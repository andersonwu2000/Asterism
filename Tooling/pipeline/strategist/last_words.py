"""The Strategist's last words after a discarded cycle (owner rulings
2026-08-30).

A proposal rebutted to the round cap is discarded and its draft is
withheld from the successor (design §3). What the successor DID keep
was the author's plan note — its beliefs — and, since `8885894e`, the
judge's rebuttals. What it still lost was the author's own knowledge
of the cycle: the computed families and numbers, the routes it now
knows are dead, the one lead it would hand over. This module asks for
exactly that, in one short turn on the SAME session (the one place the
whole debate is still in context), and stores it on the rejected rev.

Contract (`check`): three sections — `## Facts` (kernel/sampling
results, numbers, families), `## Dead routes` (what died, where),
`## Most valuable` (the one thing the successor must not lose) — at
most `LIMIT` characters, and no route: a `## Roadmap` / `NOW` /
`AHEAD` header (or an Argument/Proof section) is what anchors the next
author to a plan instead of to facts, so a note carrying one is
dropped, not repaired. Over the cap the author gets ONE turn to cut;
then the framework cuts.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

BASENAME = "_last_words.md"
LIMIT = 1000
REQUIRED = ("## Facts", "## Dead routes", "## Most valuable")
_FORBIDDEN_HEADERS = re.compile(
    r"^\s*(?:#{1,6}\s*(?:Roadmap|Argument|Proof|Conventions)\b"
    r"|(?:NOW|AHEAD|PAST)\s*$)",
    re.MULTILINE | re.IGNORECASE)


def check(text: str) -> "tuple[bool, str]":
    """(ok, reason) — reason ∈ {'', 'forbidden_header', 'missing_section',
    'too_long'}; the first defect in that order (a route is dropped
    before length is even measured)."""
    if _FORBIDDEN_HEADERS.search(text or ""):
        return False, "forbidden_header"
    if any(h not in (text or "") for h in REQUIRED):
        return False, "missing_section"
    if len(text) > LIMIT:
        return False, "too_long"
    return True, ""


def truncate(text: str) -> str:
    """Cut to the cap on a line boundary when one exists inside it."""
    if len(text) <= LIMIT:
        return text
    cut = text[:LIMIT]
    nl = cut.rfind("\n")
    return (cut[:nl] if nl > LIMIT // 2 else cut).rstrip() + "\n"


def collect(*, spawn: Callable, attempts_dir: Path, problem_dir: Path,
            workspace: Path, sid: str, mcp_config_path: "Path | None",
            timeout_sec: int, rounds: int) -> Optional[str]:
    """Run the last-words turn (and at most one cutting retry). Returns
    the note, or None: no file (the author wrote nothing), a spawn
    failure, or a note with a route (dropped and recorded degraded).
    Never raises — the discard record it decorates is best-effort."""
    from .. import PROMPT_DIR
    from ...core import degraded as _degraded
    prompt_path = PROMPT_DIR / "strategist" / "last_words.md"
    out = attempts_dir / BASENAME
    text: "str | None" = None
    for attempt in (0, 1):
        try:
            out.unlink()
        except OSError:
            pass
        flags = {"too_long": attempt == 1}
        try:
            rc = spawn(kind="strategist", prompt_path=prompt_path,
                       problem_dir=problem_dir, attempts_dir=attempts_dir,
                       session_id=sid, continuation=True,
                       timeout_sec=timeout_sec,
                       mcp_config_path=mcp_config_path,
                       prompt_flags=flags)
        except Exception as exc:  # noqa: BLE001 — never fail the discard
            print(f"[last-words] spawn raised {type(exc).__name__}: {exc}",
                  flush=True)
            return None
        if rc != 0:
            print(f"[last-words] turn rc={rc} — no note", flush=True)
            return None
        try:
            text = out.read_text(encoding="utf-8").strip("\n") + "\n"
        except OSError:
            print("[last-words] the author wrote no note", flush=True)
            return None
        ok, why = check(text)
        if ok:
            return text
        if why == "too_long" and attempt == 0:
            print(f"[last-words] {len(text)} chars > {LIMIT} — one turn to cut",
                  flush=True)
            continue
        if why == "too_long":
            print(f"[last-words] still {len(text)} chars — truncated to {LIMIT}",
                  flush=True)
            return truncate(text)
        _degraded.record(workspace, "last_words",
                         f"{why} after {rounds} round(s) — note dropped")
        print(f"[last-words] {why} — note dropped (recorded degraded)", flush=True)
        return None
    return text
