"""Lake stderr → actionable hints for the next agent invocation.

Models with stale Mathlib knowledge (older training cutoffs, or models
that prefer specific imports over the umbrella) repeatedly hit the
same classes of error: bad import paths, renamed identifiers, removed
tactics. Raw lake stderr alone does not always tell the agent how to
correct these — `error: bad import 'X.Y.Z'` reads like a plain
not-found, but the actionable response is "use `import Mathlib`
umbrella, or check current Mathlib path".

`parse_lake_stderr` extracts known error patterns and returns short
human-readable hints. Pipelines append these to `failure_detail` so
that on the next attempt, the dead_attempts → Context.md injection
shows the agent both the raw error and a structured suggestion.

This is framework-side learning that survives Mathlib evolution:
adding a new pattern is one regex, not a per-model prompt addendum.
"""
from __future__ import annotations

import re


_BAD_IMPORT_RE = re.compile(r"bad import ['`]([^'`\s]+)['`]")
_UNKNOWN_IDENT_RE = re.compile(r"unknown identifier ['`]([^'`]+)['`]")
_UNKNOWN_CONSTANT_RE = re.compile(r"unknown constant ['`]([^'`]+)['`]")
_UNKNOWN_TACTIC_RE = re.compile(r"unknown tactic ['`]([^'`]+)['`]")
_NO_FILE_RE = re.compile(
    r"no such file or directory.*?Mathlib[/\\]([A-Za-z0-9/\\.]+\.lean)",
    re.DOTALL,
)


def parse_lake_stderr(stderr: str) -> list[str]:
    """Return actionable hints derived from `stderr`. Empty list when
    no known pattern matched (silent — caller still has raw stderr).
    De-duplicated; preserves first-seen order."""
    if not stderr:
        return []

    hints: list[str] = []
    seen: set[str] = set()

    def add(hint: str) -> None:
        if hint not in seen:
            seen.add(hint)
            hints.append(hint)

    # Bad import path. Mathlib has reorganized many files into
    # subdirectories (e.g. Data.Nat.Prime → Data.Nat.Prime.Basic).
    # Safest fix: import the umbrella.
    for m in _BAD_IMPORT_RE.finditer(stderr):
        path = m.group(1)
        add(
            f"Bad import path `{path}` — this module does not exist. "
            f"Mathlib has been reorganized; the safest fix is to use "
            f"`import Mathlib` (umbrella) instead of a specific path. "
            f"If you need a smaller import, check "
            f"`.lake/packages/mathlib/Mathlib/` for the renamed module."
        )

    # `no such file` from lake build trace, which often co-occurs with
    # the above but also fires for files outside `bad import`.
    for m in _NO_FILE_RE.finditer(stderr):
        path = m.group(1).replace("\\", "/")
        add(
            f"Mathlib file not found: `Mathlib/{path}`. The file was "
            f"likely renamed or split. Use `import Mathlib` (umbrella) "
            f"or search the current Mathlib for the new location."
        )

    # Unknown identifier / constant. Could be a renamed lemma, a
    # missing import, or a typo. We don't try to guess the new name —
    # just point the agent at where to look.
    for m in _UNKNOWN_IDENT_RE.finditer(stderr):
        name = m.group(1)
        add(
            f"Unknown identifier `{name}` — the lemma/definition may "
            f"have been renamed in current Mathlib, or its module is "
            f"not imported. Try grep'ing `.lake/packages/mathlib/Mathlib/` "
            f"for similar names."
        )
    for m in _UNKNOWN_CONSTANT_RE.finditer(stderr):
        name = m.group(1)
        add(
            f"Unknown constant `{name}` — the lemma/definition may "
            f"have been renamed or removed. Search current Mathlib for "
            f"a renamed version, or use a broader import."
        )

    # Unknown tactic. Mathlib's tactic library evolves; some tactics
    # are renamed or moved.
    for m in _UNKNOWN_TACTIC_RE.finditer(stderr):
        name = m.group(1)
        add(
            f"Unknown tactic `{name}` — the tactic may have been renamed "
            f"or moved to a different module. Try `import Mathlib` "
            f"(umbrella) to ensure all tactics are in scope."
        )

    return hints


def annotate_failure_detail(failure_detail: str) -> str:
    """Append structured hint section to `failure_detail` if any pattern
    matched. Original stderr preserved verbatim above the hint block."""
    hints = parse_lake_stderr(failure_detail or "")
    if not hints:
        return failure_detail
    bullet = "\n".join(f"- {h}" for h in hints)
    return (
        f"{failure_detail}\n\n"
        f"--- framework hints (parsed from stderr) ---\n"
        f"{bullet}"
    )
