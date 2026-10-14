"""Proved-problem regression manifest (arch-review task #8).

A problem that reaches a terminal milestone gets ONE JSONL line appended
to the git-TRACKED `Benchmarks/proved_manifest.jsonl` — automatically, at
the milestone commit itself (mechanism, not operator discipline):

  * `terminal="ingested"` — the Strategist's Ingest landed (the problem's
    terminal judgment; `problems.ingested_at`);
  * `terminal="refuted"`  — the root was DISPROVED in the kernel and the
    Ingest closed the problem the other way (owner ruling 2026-08-30;
    `problems.state='refuted'`, stamped with `ingested_at` like any
    terminal). A settled root is a result whichever way it settled, and
    "which problems were ever settled, at which commit, on which
    toolchain" is exactly what this file is for.

Why it exists: the DB resets (dev-scratch), the
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

#: `refuted` was missing here from 2026-08-30 (when the owner made a
#: kernel-disproved root a terminal) to 2026-09-08. `strategist/commit`
#: called `record_terminal(terminal="refuted")` all along, so the assert
#: below tripped and the append was swallowed by the best-effort except
#: — one printed line, no milestone. Nobody hit it because no root was
#: ever disproved in that window: the certification probe was broken the
#: whole time (`9ba21ce3`), and the lab's first `false_root_e2e` run
#: found this the moment the road opened.
#: `bridged` (the retired Librarian's harvest milestone) is no longer
#: written; manifest lines that carry it read as an ingested terminal.
TERMINALS = ("ingested", "refuted")


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
                    deliverables: int = 0,
                    note: str = "",
                    settings: "dict | None" = None) -> None:
    """Append one milestone line. Best-effort by contract — any failure
    prints loudly and returns (the milestone itself already committed).
    `settings` (frontmatter dissolve): the EFFECTIVE machine settings
    at the milestone — the git-auditable record of the axiom whitelist
    now that the yaml lines no longer change."""
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
        }
        if note:
            entry["note"] = note
        if settings:
            entry["settings"] = settings
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
            "SELECT ingested_at FROM problems"
            " WHERE name = ?", (problem,)).fetchone()
        ingested = bool(row and row["ingested_at"])
        want = str(e.get("terminal"))
        if row is None or not ingested:
            out.append(("RESET", f"{problem}: recorded {want} "
                                 f"@ {e.get('commit')} but absent/reset in "
                                 f"the current DB — re-verification candidate"))
            continue
        if str(e.get("toolchain")) != cur_fp:
            out.append(("DRIFT", f"{problem}: last verified on toolchain "
                                 f"{e.get('toolchain')} ≠ current {cur_fp} — "
                                 f"not re-verified since the bump"))
            continue
        out.append(("OK", f"{problem}: {want} (still holds)"))
    return out
