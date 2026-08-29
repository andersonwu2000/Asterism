"""Silent-degradation ledger — the health signal for "non-fatal" failures.

A best-effort step that fails and logs one line is invisible to every
reader but the log grep (dedupe's defeq probe fail-opened for days on
WinError 206, 2026-08-29: `pre-flight lake build failed (non-fatal)` →
all 9,696 pairs refused, alias=0, and nobody noticed). Any such step
records here instead; `daemon status` renders the ledger as `degraded`
so the hourly patrol sees it without reading logs.

Shape (`.asterism/degraded.json`, per daemon run — reset at boot):

    {"<kind>": {"count": N, "last_at": "<iso utc>", "last_detail": "..."}}

`kind` is a stable snake_case token (grep-able, chart-able); `detail` is
the first 200 chars of the failure text. Writes are tmp + os.replace so
the status reader (a separate process) never sees a torn file; a
process-local lock serialises same-process writers. Recording never
raises — a health signal must not become a new failure path.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
_DETAIL_CAP = 200


def ledger_path(workspace: Path) -> Path:
    return workspace / ".asterism" / "degraded.json"


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, path)


def record(workspace: Path, kind: str, detail: str = "") -> None:
    """Count one occurrence of `kind`; keep the latest detail. Never raises."""
    try:
        path = ledger_path(workspace)
        with _LOCK:
            data = _load(path)
            entry = data.get(kind)
            if not isinstance(entry, dict):
                entry = {"count": 0}
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds")
            entry["last_detail"] = " ".join(str(detail).split())[:_DETAIL_CAP]
            data[kind] = entry
            _store(path, data)
    except Exception:  # noqa: BLE001 — a health signal must not raise
        pass


def snapshot(workspace: Path) -> dict:
    """The ledger as a dict (empty when nothing degraded). Read-only."""
    return _load(ledger_path(workspace))


def reset(workspace: Path) -> None:
    """Start a fresh ledger (daemon boot): the status describes THIS run."""
    try:
        path = ledger_path(workspace)
        with _LOCK:
            if path.exists():
                path.unlink()
    except OSError:
        pass
