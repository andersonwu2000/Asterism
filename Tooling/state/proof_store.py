"""Single chokepoint for every mutation of a problem's proof artifacts
(`Problems/<p>/proofs/L_*.lean`, `_strategy_s*.lean`, the goal's own `.lean`).

WHY THIS EXISTS — the DB↔file drift class. `asterism.db` is the rich state SoT
(graph, status), the `.lean` files hold the proof content. Two stores, and every
mutation must move BOTH. When file writes are scattered and not atomic with the
DB, they diverge: orphan files (write succeeds, row never committed), missing
files (row alive, file gone / clobbered), status drift (`status='proved'` but the
file carries `sorry`), and clobber (a placement overwrites another goal's
committed file). CLAUDE.md rule 10 ("recovery scripts must update DB+file in
pairs") is the human-discipline patch for exactly this.

This module makes the drift class STRUCTURAL, not discipline-enforced:
  * `atomic_write` — torn-write-safe primitive (tmp + os.replace), generalised
    from the old `promote_to_alias`.
  * `assert_writable` / `place_proof` — OWNERSHIP guard: a proof path may only be
    written by the goal that owns it in the DB (`goals.lean_path` is UNIQUE).
    A placement that would clobber a DIFFERENT goal's file raises `ClobberError`
    BEFORE touching disk — the clobber-then-orphan window cannot open.
  * `inventory` — the single DB↔file consistency oracle (the `drift_inventory`
    CLAUDE.md rule 10 already names): orphan / missing / status-drift in one
    report, reused by the CLI gate, CI, and startup recovery.

All mutators take the caller's `conn` so the file write and the DB row move
inside one logical commit; a lint test forbids raw `write_text`/`unlink` to
`proofs/` outside this module.
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import db


class ClobberError(Exception):
    """A proof-file write was refused because the path is owned by a different
    goal — the structural guard against the placement-clobber drift."""


def _norm(rel: "str | Path") -> str:
    """Workspace-relative path in the posix form the DB stores (`lean_path`)."""
    return str(rel).replace("\\", "/")


# ---------------------------------------------------------------------
# Atomic file primitive (generalised from _skeleton.promote_to_alias)
# ---------------------------------------------------------------------

def atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` torn-write-safely (tmp + os.replace): a reader
    never sees a half-written file, and a crash leaves either the old file fully
    intact or the new one fully in place. The atomic rename IS the whole
    guarantee — no persistent `.psbak` copy is kept. (An earlier verify-window
    API returned a `.psbak` backup for a caller-driven rollback/commit, but no
    call site ever adopted it: every caller discards the return, and Builder
    rolls back by re-writing the original text it kept in memory. The unreaped
    backups just leaked `Root.lean.psbak<pid>` / `L_*.lean.psbak<pid>` files.)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".pstmp{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------
# Ownership guard (the clobber-prevention core)
# ---------------------------------------------------------------------

def path_owner(conn: sqlite3.Connection, rel_path: "str | Path") -> "int | None":
    """Goal id that owns `rel_path` (`goals.lean_path`), or None if unowned."""
    r = conn.execute("SELECT id FROM goals WHERE lean_path = ?",
                     (_norm(rel_path),)).fetchone()
    return int(r[0]) if r else None


def assert_writable(conn: sqlite3.Connection, rel_path: "str | Path", *,
                    owner_goal_id: "int | None") -> None:
    """Raise `ClobberError` if a DIFFERENT goal owns `rel_path`. `owner_goal_id`
    is the goal the caller intends to write for (None = a fresh placement that
    must own no existing path)."""
    owner = path_owner(conn, rel_path)
    if owner is not None and owner != owner_goal_id:
        raise ClobberError(
            f"refusing to write {_norm(rel_path)}: owned by goal {owner}, "
            f"not {owner_goal_id} (placement clobber guard)")


def place_proof(conn: sqlite3.Connection, workspace: Path, *,
                goal_id: "int | None", rel_path: "str | Path",
                content: str) -> None:
    """Ownership-guarded atomic write of a proof file for `goal_id`. Refuses to
    clobber another goal's file (`assert_writable`), then writes torn-write-safely
    (`atomic_write`)."""
    assert_writable(conn, rel_path, owner_goal_id=goal_id)
    atomic_write(workspace / _norm(rel_path), content)


def remove_proof(conn: sqlite3.Connection, workspace: Path, *,
                 rel_path: "str | Path",
                 owner_goal_id: "int | None") -> None:
    """Ownership-guarded delete: never unlink a file owned by a different goal
    (the failed-cleanup-deletes-a-committed-stub drift)."""
    assert_writable(conn, rel_path, owner_goal_id=owner_goal_id)
    (workspace / _norm(rel_path)).unlink(missing_ok=True)


# ---------------------------------------------------------------------
# Consistency oracle — `drift_inventory` (CLAUDE.md rule 10)
# ---------------------------------------------------------------------

# `sorry` / `admit` as a whole token in CODE (not comments) — a `proved` file
# carrying one is a silent fake proof that propagates to the root.
_SORRY_RE = re.compile(r"\b(sorry|admit)\b")
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/-.*?-/", re.S)
_PROOF_IMPORT_RE = re.compile(r"(?m)^\s*import\s+([\w.]+)")


def _strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", text))


def _has_sorry(text: str) -> bool:
    return bool(_SORRY_RE.search(_strip_comments(text)))


def _git_untracked_under(workspace: Path, rel_dir: str) -> "set[str] | None":
    """Posix rel-paths under `rel_dir` that git does NOT track (untracked or
    ignored). None when not a git repo (callers then treat all as untracked).
    Committed proof files are protected — only never-committed placement orphans
    are deletable."""
    try:
        r = subprocess.run(
            ["git", "ls-files", "--others", "--", rel_dir],
            cwd=str(workspace), capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        return {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
    except Exception:  # noqa: BLE001 — not a repo / git missing → caller default
        return None


@dataclass
class DriftReport:
    """DB↔file correspondence violations for one (optionally scoped) run."""
    orphan_files: "list[str]" = field(default_factory=list)      # file, no row
    missing_files: "list[str]" = field(default_factory=list)     # row, no file
    proved_with_sorry: "list[str]" = field(default_factory=list)  # status drift

    def ok(self) -> bool:
        return not (self.orphan_files or self.missing_files
                    or self.proved_with_sorry)

    def summary(self) -> str:
        if self.ok():
            return "DB↔file consistent (no drift)"
        parts = []
        if self.orphan_files:
            parts.append(f"{len(self.orphan_files)} orphan file(s) (no DB row)")
        if self.missing_files:
            parts.append(f"{len(self.missing_files)} missing file(s) (row, no file)")
        if self.proved_with_sorry:
            parts.append(f"{len(self.proved_with_sorry)} proved-with-sorry file(s)")
        return "; ".join(parts)


def inventory(conn: sqlite3.Connection, workspace: Path, *,
              scope: "str | None" = None) -> DriftReport:
    """The single DB↔file consistency oracle. Reports:
      - orphan_files: `proofs/L_*.lean` / `_strategy_s*.lean` present + git-
        untracked + backed by NO DB row (placement crashed before the commit).
      - missing_files: a goal past 'open' (attempting/proved/shelved) whose
        `lean_path` file is absent (clobbered / failed-cleanup deletion).
      - proved_with_sorry: a `status='proved'` goal whose file carries a `sorry`
        in code — a silent fake proof.
    `scope` (a `problem LIKE` pattern) limits the sweep to the daemon's scope."""
    rep = DriftReport()
    problems = [r["problem"] for r in conn.execute(
        "SELECT DISTINCT problem FROM goals"
        + (" WHERE problem LIKE ?" if scope else ""),
        ((scope,) if scope else ()))]
    for problem in problems:
        rows = list(conn.execute(
            "SELECT id, lean_path, status FROM goals WHERE problem = ?"
            " AND lean_path IS NOT NULL", (problem,)))
        known: "set[str]" = {_norm(r["lean_path"]) for r in rows}
        for r in conn.execute(
                "SELECT s.lean_path AS lp, s.scratch_path AS sp"
                " FROM strategies s JOIN goals g ON g.id = s.goal_id"
                " WHERE g.problem = ?", (problem,)):
            if r["lp"]:
                known.add(_norm(r["lp"]))
            if r["sp"]:
                known.add(_norm(r["sp"]))
        # missing / status drift — driven by DB rows
        for r in rows:
            rel = _norm(r["lean_path"])
            f = workspace / rel
            if not f.exists():
                if r["status"] in ("attempting", "proved", "shelved"):
                    rep.missing_files.append(rel)
                continue
            if r["status"] == "proved":
                try:
                    if _has_sorry(f.read_text(encoding="utf-8", errors="replace")):
                        rep.proved_with_sorry.append(rel)
                except OSError:
                    pass
        # orphan files — driven by disk
        proofs_dir = db.problem_dir(workspace, problem) / "proofs"
        if not proofs_dir.exists():
            continue
        untracked = _git_untracked_under(
            workspace, proofs_dir.relative_to(workspace).as_posix())
        files = (sorted(proofs_dir.glob("L_*.lean"))
                 + sorted(proofs_dir.glob("_strategy_s*.lean")))
        for fp in files:
            rel = fp.relative_to(workspace).as_posix()
            if rel in known:
                continue
            if untracked is not None and rel not in untracked:
                continue                         # committed file → protected
            rep.orphan_files.append(rel)
    return rep
