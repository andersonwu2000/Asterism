"""Proved-problem regression manifest (arch-review task #8).

A problem that reaches a terminal milestone gets ONE JSONL line appended
to the git-TRACKED `Benchmarks/proved_manifest.jsonl` — automatically, at
the milestone commit itself (mechanism, not operator discipline):

  * `terminal="ingested"` — the Strategist's Ingest landed (the problem's
    terminal judgment; `problems.ingested_at`);
  * `terminal="bridged"`  — bridge/Gate B PASSED (the harvest is in the
    Library; `problems.library_bridged_at`).

Why it exists: the DB resets (dev-scratch), the Library resets, the
README progress log is prose, and INDEX.md (the one git-tracked
provenance) retired in v18 — so "which problems were EVER proved, at
which commit, on which toolchain" was not reconstructable, and a
framework regression that silently un-proves a previously-proved problem
was only caught by accidental re-runs. docs/errata versions the
FALSIFICATION artifacts; this is the same value applied to the positive
results.

Append-only: re-proving a problem appends another line (history is the
record; nothing rewrites it). `asterism regress` compares the manifest
against the CURRENT workspace as a REPORT (a reset problem is a
re-verification CANDIDATE, not an error — resets are routine).

Every writer is best-effort: a manifest write must never fail a proving
or harvest pipeline.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..core.process_group import no_window_creationflags

MANIFEST_REL = Path("Benchmarks") / "proved_manifest.jsonl"

TERMINALS = ("ingested", "bridged")


def _git_head(workspace: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(workspace), capture_output=True, text=True, timeout=10,
            creationflags=no_window_creationflags())
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def record_terminal(workspace: Path, *, problem: str, terminal: str,
                    deliverables: int = 0, harvest_files: int = 0,
                    note: str = "") -> None:
    """Append one milestone line. Best-effort by contract — any failure
    prints loudly and returns (the milestone itself already committed)."""
    try:
        from ..quality.lean_contracts import toolchain_fingerprint
        from .db import now
        assert terminal in TERMINALS, terminal
        entry = {
            "problem": problem,
            "terminal": terminal,
            "commit": _git_head(workspace) or "unknown",
            "toolchain": toolchain_fingerprint(workspace)[:16],
            "at": now(),
            "deliverables": int(deliverables),
            "harvest_files": int(harvest_files),
        }
        if note:
            entry["note"] = note
        path = workspace / MANIFEST_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"[regress] recorded {problem} → {terminal} "
              f"@ {entry['commit']}", flush=True)
    except Exception as e:  # noqa: BLE001 — never block the milestone
        print(f"[regress] manifest append FAILED for {problem} "
              f"({type(e).__name__}: {e}) — milestone unaffected",
              flush=True)


def load(workspace: Path) -> "list[dict]":
    path = workspace / MANIFEST_REL
    if not path.is_file():
        return []
    out: "list[dict]" = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            out.append(json.loads(ln))
    return out


def report(conn, workspace: Path) -> "list[tuple[str, str]]":
    """Manifest vs current workspace — [(status, message)]. Statuses:
      RESET     recorded terminal, current DB has none → re-verify CANDIDATE
      PARTIAL   recorded bridged, DB has only ingested (harvest undone)
      DRIFT     current toolchain differs from the last recorded line's
      OK        recorded terminal still holds
    Report semantics only — resets are a normal workflow, not failures."""
    from ..quality.lean_contracts import toolchain_fingerprint
    cur_fp = toolchain_fingerprint(workspace)[:16]
    # last recorded line per problem wins (append-only history)
    latest: "dict[str, dict]" = {}
    for e in load(workspace):
        latest[str(e.get("problem", ""))] = e
    out: "list[tuple[str, str]]" = []
    for problem, e in sorted(latest.items()):
        row = conn.execute(
            "SELECT ingested_at, library_bridged_at FROM problems"
            " WHERE name = ?", (problem,)).fetchone()
        ingested = bool(row and row["ingested_at"])
        bridged = bool(row and row["library_bridged_at"])
        want = str(e.get("terminal"))
        if row is None or not (ingested or bridged):
            out.append(("RESET", f"{problem}: recorded {want} "
                                 f"@ {e.get('commit')} but absent/reset in "
                                 f"the current DB — re-verification candidate"))
            continue
        if want == "bridged" and not bridged:
            out.append(("PARTIAL", f"{problem}: recorded bridged but only "
                                   f"ingested now (harvest undone?)"))
            continue
        if str(e.get("toolchain")) != cur_fp:
            out.append(("DRIFT", f"{problem}: last verified on toolchain "
                                 f"{e.get('toolchain')} ≠ current {cur_fp} — "
                                 f"not re-verified since the bump"))
            continue
        out.append(("OK", f"{problem}: {want} (still holds)"))
    return out
