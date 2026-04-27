"""CommitWriter: two-phase commit protocol (impl §1).

Three-step protocol (INSERT or UPDATE):
  Step 1 (begin)       – DB TX: mark row commit_state='pending'
  Step 2 (stage_file)  – mv staging .lean → lean_path (idempotent)
  Step 3 (finalize)    – DB TX: set commit_state='live', apply final_fields

COMMIT_FAULT env var: inject faults for test reproducibility.
  COMMIT_FAULT=after_step1 | after_step2 | after_step3
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Only goals has updated_at; strategies does not.
_TABLES_WITH_UPDATED_AT: frozenset[str] = frozenset({"goals"})


class CommitFault(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_fault(stage: str) -> None:
    mode = os.environ.get("COMMIT_FAULT", "")
    if mode == stage:
        raise CommitFault(f"COMMIT_FAULT={mode}")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommitWriter:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------
    # Step 1
    # ------------------------------------------------------------------

    def begin(
        self,
        table: str,
        op: str,
        data: dict[str, Any] | None = None,
        row_id: int | None = None,
    ) -> int:
        """Step 1: mark row pending.

        op='insert': INSERT row with commit_state='pending'. Returns new ID.
        op='update': snapshot existing row → prior_state_snapshot, set
                     commit_state='pending'. Returns same row_id.
        """
        now = _now()
        if op == "insert":
            fields = dict(data or {})
            fields["commit_state"] = "pending"
            fields["prior_state_snapshot"] = None
            fields.setdefault("created_at", now)
            if table in _TABLES_WITH_UPDATED_AT:
                fields.setdefault("updated_at", now)
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" * len(fields))
            with self.conn:
                cur = self.conn.execute(
                    f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                    list(fields.values()),
                )
                new_id = cur.lastrowid
            _check_fault("after_step1")
            return new_id  # type: ignore[return-value]

        elif op == "update":
            if row_id is None:
                raise ValueError("row_id required for op='update'")
            cur = self.conn.execute(
                f"SELECT * FROM {table} WHERE id = ?", (row_id,)
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Row {row_id} not found in {table}")
            col_names = [d[0] for d in cur.description]
            snapshot = json.dumps(dict(zip(col_names, row)))

            set_parts = ["commit_state = 'pending'", "prior_state_snapshot = ?"]
            params: list[Any] = [snapshot]
            if table in _TABLES_WITH_UPDATED_AT:
                set_parts.append("updated_at = ?")
                params.append(now)
            params.append(row_id)
            with self.conn:
                self.conn.execute(
                    f"UPDATE {table} SET {', '.join(set_parts)} WHERE id = ?",
                    params,
                )
            _check_fault("after_step1")
            return row_id

        else:
            raise ValueError(f"Unknown op: {op!r}")

    def begin_batch(self, ops: list[dict[str, Any]]) -> list[int]:
        """Step 1 (multi-row): multiple begin ops in a single TX.

        Each op: {'table': str, 'op': 'insert'|'update', 'data': dict}
              or {'table': str, 'op': 'update', 'id': int}
        Returns list of row IDs in ops order.
        """
        now = _now()
        ids: list[int] = []

        with self.conn:
            for op_spec in ops:
                table = op_spec["table"]
                op = op_spec["op"]

                if op == "insert":
                    fields = dict(op_spec.get("data", {}))
                    fields["commit_state"] = "pending"
                    fields["prior_state_snapshot"] = None
                    fields.setdefault("created_at", now)
                    if table in _TABLES_WITH_UPDATED_AT:
                        fields.setdefault("updated_at", now)
                    cols = ", ".join(fields.keys())
                    placeholders = ", ".join("?" * len(fields))
                    cur = self.conn.execute(
                        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                        list(fields.values()),
                    )
                    ids.append(cur.lastrowid)  # type: ignore[arg-type]

                elif op == "update":
                    rid = op_spec["id"]
                    cur = self.conn.execute(
                        f"SELECT * FROM {table} WHERE id = ?", (rid,)
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise ValueError(f"Row {rid} not found in {table}")
                    col_names = [d[0] for d in cur.description]
                    snapshot = json.dumps(dict(zip(col_names, row)))

                    set_parts = ["commit_state = 'pending'", "prior_state_snapshot = ?"]
                    params: list[Any] = [snapshot]
                    if table in _TABLES_WITH_UPDATED_AT:
                        set_parts.append("updated_at = ?")
                        params.append(now)
                    params.append(rid)
                    self.conn.execute(
                        f"UPDATE {table} SET {', '.join(set_parts)} WHERE id = ?",
                        params,
                    )
                    ids.append(rid)

                else:
                    raise ValueError(f"Unknown op: {op!r}")

        _check_fault("after_step1")
        return ids

    # ------------------------------------------------------------------
    # Step 2
    # ------------------------------------------------------------------

    def stage_file(self, src: str | Path, dst: str | Path) -> None:
        """Step 2: mv staging file to lean_path (idempotent).

        Idempotent: skip if dst already exists with same hash as src,
        or if src is gone (move already completed).
        """
        src, dst = Path(src), Path(dst)
        if dst.exists():
            if not src.exists() or _file_hash(dst) == _file_hash(src):
                _check_fault("after_step2")
                return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        _check_fault("after_step2")

    # ------------------------------------------------------------------
    # Step 3
    # ------------------------------------------------------------------

    def finalize(
        self, table: str, row_id: int, final_fields: dict[str, Any]
    ) -> None:
        """Step 3: set commit_state='live', apply final_fields, clear snapshot."""
        now = _now()
        updates = dict(final_fields)
        updates["commit_state"] = "live"
        updates["prior_state_snapshot"] = None
        if table in _TABLES_WITH_UPDATED_AT:
            updates["updated_at"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self.conn:
            self.conn.execute(
                f"UPDATE {table} SET {set_clause} WHERE id = ?",
                list(updates.values()) + [row_id],
            )
        _check_fault("after_step3")

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def recover_scan(self) -> dict[str, list[int]]:
        """Scan goals + strategies for pending rows and recover (impl §1.3).

        Rules per pending row:
          lean_path exists on disk          → finalize (step 3 idempotent)
          lean_path absent + snapshot NULL  → DELETE row  (INSERT, step 1 only)
          lean_path absent + snapshot set   → restore from snapshot (UPDATE)

        Returns {table: [recovered_row_ids]}.
        """
        recovered: dict[str, list[int]] = {"goals": [], "strategies": []}

        for table in ("goals", "strategies"):
            rows = self.conn.execute(
                f"SELECT id, lean_path, prior_state_snapshot "
                f"FROM {table} WHERE commit_state = 'pending'"
            ).fetchall()

            for row_id, lean_path, snapshot in rows:
                lean_path_obj = Path(lean_path) if lean_path else None
                lean_exists = lean_path_obj is not None and lean_path_obj.exists()

                if lean_exists:
                    # Step 2 done; the file is already at lean_path. Spec §1.3
                    # rule 1 says "重跑 mv（idempotent）" but the staging-source
                    # path is not stored in the schema, so we cannot literally
                    # re-invoke stage_file here. shutil.move/os.replace is atomic,
                    # so dst-exists implies step 2 succeeded — we go straight to
                    # finalize for the equivalent terminal state. P2+ would need
                    # a staging_path column to restore the literal "rerun mv".
                    self.finalize(table, row_id, {})
                    recovered[table].append(row_id)

                elif snapshot is None:
                    # INSERT interrupted before step 2: delete pending row.
                    with self.conn:
                        self.conn.execute(
                            f"DELETE FROM {table} WHERE id = ?", (row_id,)
                        )
                    recovered[table].append(row_id)

                else:
                    # UPDATE interrupted before step 2: restore from snapshot.
                    snap: dict[str, Any] = json.loads(snapshot)
                    snap.pop("id", None)
                    snap["prior_state_snapshot"] = None
                    if table in _TABLES_WITH_UPDATED_AT:
                        snap["updated_at"] = _now()
                    set_clause = ", ".join(f"{k} = ?" for k in snap)
                    with self.conn:
                        self.conn.execute(
                            f"UPDATE {table} SET {set_clause} WHERE id = ?",
                            list(snap.values()) + [row_id],
                        )
                    recovered[table].append(row_id)

        return recovered
