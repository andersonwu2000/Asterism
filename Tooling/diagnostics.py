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


# Lean's casing is inconsistent: `unknown identifier 'foo'` (lowercase)
# vs `Unknown constant ` foo`` (capital U). re.IGNORECASE handles both.
_BAD_IMPORT_RE = re.compile(
    r"bad import ['`]([^'`\s]+)['`]", re.IGNORECASE)
_UNKNOWN_IDENT_RE = re.compile(
    r"unknown identifier ['`]([^'`]+)['`]", re.IGNORECASE)
_UNKNOWN_CONSTANT_RE = re.compile(
    r"unknown constant ['`]([^'`]+)['`]", re.IGNORECASE)
_UNKNOWN_TACTIC_RE = re.compile(
    r"unknown tactic ['`]([^'`]+)['`]", re.IGNORECASE)
# Lean's autoImplicit hint phrasing: "Hint: The identifier `X` is unknown,
# and Lean's `autoImplicit` option ..." — same root cause as a plain
# unknown identifier (missing import / typo).
_AUTOIMPLICIT_HINT_RE = re.compile(
    r"the identifier ['`]([^'`]+)['`] is unknown", re.IGNORECASE)
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

    # autoImplicit hint surfaces the same missing-import pathology as
    # `unknown identifier`, just phrased as a help message. Treat it as
    # an unknown identifier for hint-building purposes.
    for m in _AUTOIMPLICIT_HINT_RE.finditer(stderr):
        name = m.group(1)
        add(
            f"Identifier `{name}` is unknown (autoImplicit hint) — most "
            f"likely a missing `import Mathlib` at the top of the file. "
            f"Add the umbrella import or check the specific module path."
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


_IMPORTANT_LINE_RE = re.compile(
    r"^.*?(?:error[:\s]|warning[:\s]|✖|unknown identifier|unknown constant"
    r"|unknown tactic|bad import|object file).*$",
    re.MULTILINE,
)


def smart_truncate_stderr(stderr: str, *, budget: int = 2000) -> str:
    """Truncate stderr while preserving the lines diagnostics actually
    care about: errors, warnings, the lake `✖` task marker, and the
    Lean-side `unknown ...` / `bad import` / `object file ...` strings.

    Lake `lake build <module>` stderr on Windows often dumps a
    multi-kilobyte LEAN_PATH string before reaching the actual Lean
    error. A naive `stderr[:budget]` cuts off the error and
    parse_lake_stderr sees nothing to act on.

    Strategy: extract important lines first (preserve order), then
    fill the remaining budget with the head of the original stderr
    for context.
    """
    if not stderr:
        return stderr
    if len(stderr) <= budget:
        return stderr

    important = _IMPORTANT_LINE_RE.findall(stderr)
    # Dedupe consecutive identical lines while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for ln in important:
        if ln not in seen:
            seen.add(ln)
            deduped.append(ln)

    important_text = "\n".join(deduped)
    if len(important_text) >= budget:
        return important_text[:budget]

    sep = "\n--- trace head ---\n"
    head_budget = budget - len(important_text) - len(sep)
    if head_budget <= 0:
        return important_text
    return important_text + sep + stderr[:head_budget]


def annotate_failure_detail(failure_detail: str) -> str:
    """Smart-truncate stderr (preserves error lines), then append parsed
    hints if any patterns matched."""
    if not failure_detail:
        return failure_detail
    truncated = smart_truncate_stderr(failure_detail)
    hints = parse_lake_stderr(truncated)
    if not hints:
        return truncated
    bullet = "\n".join(f"- {h}" for h in hints)
    return (
        f"{truncated}\n\n"
        f"--- framework hints (parsed from stderr) ---\n"
        f"{bullet}"
    )
