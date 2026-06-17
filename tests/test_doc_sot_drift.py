"""Bind the living SoT docs to code, so they can't silently drift.

Two classes of drift this session's audit found by hand — both invisible to
every existing test:
  1. `failure_modes.md` (the declared single-source-of-truth for
     `failure_reason`) was missing ~24 values the code actually emits
     (all the `librarian_*`, a few Builder/Backward declines, Strategist).
  2. Code comments cited `pipelines.md §4.7`, a section that does not exist.

These tests re-derive both checks from the code/doc so the SoT defends
itself. Doc-only changes, but a stale SoT misleads every agent that reads
Context.md, so it's worth a gate.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "Tooling"
TESTS = ROOT / "tests"
FAILURE_MODES = ROOT / "docs" / "failure_modes.md"
PHASE2 = ROOT / "docs" / "archive" / "design" / "phase2"


def _py_files(*roots: Path) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        out += [p for p in r.rglob("*.py") if "__pycache__" not in p.parts]
    return out


# --- 1. failure_modes.md documents every failure_reason the code emits ------

# `failure_reason="x"` / `failure_reason='x'` (optional f-string prefix) and
# `_abort("x", ...)` (backward.py's terminal-decline helper, first arg).
_FR_ASSIGN = re.compile(r"""failure_reason\s*=\s*f?["']([a-z][a-z0-9_]*)["']""")
_FR_ABORT = re.compile(r"""_abort\(\s*["']([a-z][a-z0-9_]*)["']""")


def _code_failure_reasons() -> set[str]:
    reasons: set[str] = set()
    for f in _py_files(TOOLING):
        text = f.read_text(encoding="utf-8")
        reasons.update(_FR_ASSIGN.findall(text))
        reasons.update(_FR_ABORT.findall(text))
    return reasons


def test_failure_modes_documents_all_code_failure_reasons() -> None:
    doc = FAILURE_MODES.read_text(encoding="utf-8")
    missing = sorted(
        r for r in _code_failure_reasons()
        if not re.search(rf"`{re.escape(r)}`", doc) and not re.search(rf"\b{re.escape(r)}\b", doc)
    )
    assert not missing, (
        "failure_modes.md is the SoT for failure_reason but does not mention "
        "these values that the code emits — document them (see the §2 master "
        "table / Strategist+Librarian subsection):\n  " + "\n  ".join(missing))


# --- 2. every pipelines.md / design.md §-anchor cited in code exists ---------

# e.g.  `docs/archive/design/phase2/pipelines.md` §4.2   or   pipelines.md §3.4
_ANCHOR_CITE = re.compile(
    r"(pipelines|design)\.md[`'\")\s]*[§§]\s*(\d+(?:\.\d+)*)")
# markdown headers like "### 4.2 Cascade" / "## 5. Picked by ..."
_HEADER = re.compile(r"^#{1,4}\s+(\d+(?:\.\d+)*)", re.MULTILINE)


def _doc_sections(stem: str) -> set[str]:
    p = PHASE2 / f"{stem}.md"
    if not p.exists():
        return set()
    return set(_HEADER.findall(p.read_text(encoding="utf-8")))


def test_code_cited_phase2_sections_exist() -> None:
    present = {"pipelines": _doc_sections("pipelines"), "design": _doc_sections("design")}
    dangling: list[str] = []
    for f in _py_files(TOOLING, TESTS):
        if f.name == Path(__file__).name:
            continue
        for stem, sec in _ANCHOR_CITE.findall(f.read_text(encoding="utf-8")):
            # a cited "4.2" is satisfied by header 4.2 OR a parent header 4
            ok = any(s == sec or s.startswith(sec + ".") or sec.startswith(s + ".")
                     for s in present[stem])
            # also accept exact top-level (e.g. cite "3" -> header "3")
            ok = ok or sec in present[stem]
            if not ok:
                rel = f.relative_to(ROOT).as_posix()
                dangling.append(f"{rel}: cites {stem}.md §{sec} (no such section)")
    assert not dangling, (
        "code comments cite phase2 doc sections that don't exist (dangling "
        "anchor — fix the citation or the doc):\n  " + "\n  ".join(sorted(set(dangling))))
