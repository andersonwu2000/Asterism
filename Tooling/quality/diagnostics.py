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
from dataclasses import dataclass
from typing import Callable


_NAME_IDENTITY: Callable[[str], str] = lambda s: s
_NAME_NORMALIZE_PATH: Callable[[str], str] = lambda s: s.replace("\\", "/")


@dataclass(frozen=True)
class _HintPattern:
    """One stderr pattern + its hint template.

    `regex` is matched against the stderr; group(1) is the captured
    name / path. `transform` post-processes the captured group (default
    identity); `template` is a `.format(name=...)` string. Adding a new
    error pattern is one entry in `_HINT_PATTERNS` below — no new
    if-block in `parse_lake_stderr`.
    """
    regex: re.Pattern[str]
    template: str
    transform: Callable[[str], str] = _NAME_IDENTITY


# Lean's casing is inconsistent: `unknown identifier 'foo'` (lowercase)
# vs `Unknown constant ` foo`` (capital U). IGNORECASE handles both.
# Order matters for first-seen de-dup (rare collisions): bad-import and
# no-file fire first since they're the most actionable; unknown-name
# variants follow; unknown-tactic last.
_HINT_PATTERNS: list[_HintPattern] = [
    _HintPattern(
        re.compile(r"bad import ['`]([^'`\s]+)['`]", re.IGNORECASE),
        "Bad import path `{name}` — this module does not exist. "
        "Mathlib has been reorganized; the safest fix is to use "
        "`import Mathlib` (umbrella) instead of a specific path. "
        "If you need a smaller import, check "
        "`.lake/packages/mathlib/Mathlib/` for the renamed module.",
    ),
    _HintPattern(
        re.compile(
            r"no such file or directory.*?Mathlib[/\\]([A-Za-z0-9/\\.]+\.lean)",
            re.DOTALL,
        ),
        "Mathlib file not found: `Mathlib/{name}`. The file was "
        "likely renamed or split. Use `import Mathlib` (umbrella) "
        "or search the current Mathlib for the new location.",
        transform=_NAME_NORMALIZE_PATH,
    ),
    _HintPattern(
        re.compile(r"unknown identifier ['`]([^'`]+)['`]", re.IGNORECASE),
        "Unknown identifier `{name}` — the lemma/definition may "
        "have been renamed in current Mathlib, or its module is "
        "not imported. Try grep'ing `.lake/packages/mathlib/Mathlib/` "
        "for similar names.",
    ),
    _HintPattern(
        re.compile(r"unknown constant ['`]([^'`]+)['`]", re.IGNORECASE),
        "Unknown constant `{name}` — the lemma/definition may "
        "have been renamed or removed. Search current Mathlib for "
        "a renamed version, or use a broader import.",
    ),
    # autoImplicit hint surfaces the same missing-import pathology as
    # `unknown identifier`, just phrased as a help message.
    _HintPattern(
        re.compile(r"the identifier ['`]([^'`]+)['`] is unknown",
                   re.IGNORECASE),
        "Identifier `{name}` is unknown (autoImplicit hint) — most "
        "likely a missing `import Mathlib` at the top of the file. "
        "Add the umbrella import or check the specific module path.",
    ),
    _HintPattern(
        re.compile(r"unknown tactic ['`]([^'`]+)['`]", re.IGNORECASE),
        "Unknown tactic `{name}` — the tactic may have been renamed "
        "or moved to a different module. Try `import Mathlib` "
        "(umbrella) to ensure all tactics are in scope.",
    ),
]


def parse_lake_stderr(stderr: str) -> list[str]:
    """Return actionable hints derived from `stderr`. Empty list when
    no known pattern matched (silent — caller still has raw stderr).
    De-duplicated; preserves first-seen order."""
    if not stderr:
        return []
    hints: list[str] = []
    seen: set[str] = set()
    for hp in _HINT_PATTERNS:
        for m in hp.regex.finditer(stderr):
            name = hp.transform(m.group(1))
            hint = hp.template.format(name=name)
            if hint not in seen:
                seen.add(hint)
                hints.append(hint)
    return hints


_IMPORTANT_LINE_RE = re.compile(
    r"^.*?(?:error[:\s]|warning[:\s]|✖|unknown identifier|unknown constant"
    r"|unknown tactic|bad import|object file).*$",
    re.MULTILINE,
)

# Pure-noise lines lake emits in every build-error stderr. These
# carry no signal beyond what the actual `error:` line already conveys,
# but historically dominated failure_detail by 70-80% of bytes. We
# delete them outright before any reorder / truncate logic.
_NOISE_LINE_PATTERNS = [
    # `trace: .> LEAN_PATH=...lean.exe ...args... --json` single line.
    # Anchor on the LEAN_PATH= sigil; the rest of the line is the
    # full lean.exe invocation we don't need.
    r"^trace: \.> LEAN_PATH=.*$",
    # Redundant exit-code summary; the prior `error:` already explained
    # the failure. Matches "error: Lean exited with code 1" / "...code 2"
    # / `build failed` / lake's task-failure rollup.
    r"^error: Lean exited with code \d+\s*$",
    r"^error: build failed\s*$",
    r"^Some required targets logged failures:\s*$",
    # The list of failed module paths under "Some required targets".
    # In single-target builds this duplicates the ✖ Building header.
    r"^- Problems\..*$",
]
_NOISE_LINE_RE = re.compile("|".join(f"(?:{p})" for p in _NOISE_LINE_PATTERNS),
                            re.MULTILINE)


def strip_lake_noise(stderr: str) -> str:
    """Remove lake/lean infrastructure noise from stderr while keeping
    every actionable line (error / warning / Note / Hint / ✖ progress
    markers / multi-line context blocks like Type mismatch's expected
    vs actual) verbatim.

    Cuts typical lake_build_error failure_detail from ~1.4 KB down to
    ~250 B — the rest was LEAN_PATH dump + redundant exit-summary
    boilerplate carrying no information beyond the actual error line.
    """
    if not stderr:
        return stderr
    out = _NOISE_LINE_RE.sub("", stderr)
    # The substitutions leave blank lines where noise used to be.
    # Collapse runs of blank lines to at most one.
    out = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", out)
    return out.strip()


def smart_truncate_stderr(stderr: str, *, budget: int = 2000,
                          force_reorder: bool = False) -> str:
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

    `force_reorder=True` skips the under-budget fast path so the
    LEAN_PATH dump is pushed past the error line even when the whole
    stderr fits in budget. Used by companion-file writers where
    the lazy-load file's reader still benefits from error-first order.
    """
    if not stderr:
        return stderr

    # Drop lake noise lines (LEAN_PATH dump, redundant exit
    # summaries) unconditionally. Every consumer of smart_truncate
    # benefits; force_reorder remains useful for ordering whatever
    # actionable content survives.
    stderr = strip_lake_noise(stderr)

    if not force_reorder and len(stderr) <= budget:
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

    # A trace head that the reordered lines already contain is not
    # context, it is the same text twice. It happens whenever the whole
    # detail is "important" — which is the normal shape of a salvage
    # line, as opposed to the lake dump this function was written for
    # (g7491's attempt blocks carried their timeout autopsy verbatim
    # twice, once as the reorder and once as the head).
    if stderr.strip() and stderr.strip() in important_text:
        return important_text
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
