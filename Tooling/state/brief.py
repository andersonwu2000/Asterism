"""BRIEF.md — auto-rendered problem-level stable context.

Holds the cross-spawn invariants the framework would otherwise re-inject
into every Context.md: sandbox rules, forbidden lemmas, strategic
notes, Library entries.

Re-render triggers:
  * `cli init`         — create initial BRIEF when a Problem is registered.
  * daemon startup     — refresh from current Manifest + Library state
                         (covers Manifest edits + library promotes from
                         the previous run; daemon has no hot-reload).

Atomicity: write via tmp file + os.replace so an in-flight `cat
BRIEF.md` from the operator never sees a half-written file.

Compile_context inlines this file's contents into Context.md so the
agent's read surface stays single-file.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from . import db, manifest


_BRIEF_FILENAME = "BRIEF.md"


def render(workspace: Path, mfst: manifest.Manifest, conn=None) -> str:
    """Assemble the stable sections into a single markdown string.

    Order:
      1. Sandbox (read scope / output file conventions)
      2. FORBIDDEN_LEMMAS
      3. Strategic notes
      4. Library available
    """
    # Late import: context → pipeline → agent → context cycle would
    # break a top-level import here. brief.render is only ever called
    # off the dispatch path (cli init / daemon startup), so the
    # one-time cost of the lazy import is moot.
    from ..agent import context
    sections: list[list[str]] = [
        _section_brief_header(mfst),
        context._section_sandbox(),
        context._section_manifest_forbidden(mfst),
        context._section_manifest_notes(mfst),
        context._section_library_available(conn, mfst),
    ]
    parts: list[str] = []
    for s in sections:
        parts.extend(s)
    return "\n".join(parts)


def write(workspace: Path, mfst: manifest.Manifest,
          conn=None) -> Path | None:
    """Write the rendered BRIEF to `Problems/<problem>/BRIEF.md`. Atomic
    via tmp-file + os.replace. Returns the path written, or None if the
    Problem dir does not exist (test fixtures, mid-reset races)."""
    pdir = db.problem_dir(workspace, mfst.problem)
    if not pdir.exists():
        return None
    target = pdir / _BRIEF_FILENAME
    content = render(workspace, mfst, conn=conn)
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp", prefix="BRIEF.", dir=str(pdir),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise
    return target


def write_for_all_problems(conn: sqlite3.Connection, workspace: Path,
                            manifests: dict[str, manifest.Manifest]) -> None:
    """Re-render BRIEF for every registered problem. Called at daemon
    startup so any Manifest edits / Library promotes since the last run
    land in BRIEF before the first dispatch.
    """
    for problem_name, mfst in manifests.items():
        try:
            write(workspace, mfst)
        except Exception as exc:  # noqa: BLE001
            # BRIEF render failure must not block the daemon. Log and
            # carry on — Context.md will inline whatever's currently on
            # disk (or empty fallback).
            print(f"[brief] {problem_name}: write skipped — {exc}",
                  flush=True)


def _section_brief_header(mfst: manifest.Manifest) -> list[str]:
    return [
        f"# {mfst.problem} — BRIEF",
        "",
        f"_Auto-rendered from `Manifest.md` + `Library/`. The framework_",
        f"_inlines this file into `Context.md` for every Builder /_",
        f"_Backward dispatch on this problem._",
        "",
    ]
