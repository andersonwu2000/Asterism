"""Assembly gate — verify Backward strategy patches have no residual
`sorry` placeholder in their body before sub-goal dispatch.

Background: Backward agent's job is to decompose a parent goal into
sub-goals. The prompt asks the agent to:
  (1) prototype the decomposition with `have h_<slug> : <stmt> := by sorry`
      placeholders (just to type-check the combinator),
  (2) write each `new_<slug>.lean` stub, and
  (3) replace each placeholder with `have h_<slug> := <slug> <args>`
      (a real reference to the extracted theorem).

If the agent skips step 3, the strategy patch ships with `:= by sorry`
in the proof body. `verify_strategy` is mechanical (promote_to_alias
only — no axiom check), so the sorry-bearing strategy is recorded as
'succeeded'. The goal flips to 'proved' in the DB and Root.lean becomes
an alias to a tainted proof.

Historically the only safety net was `library.maybe_promote`'s root
axiom_probe (sorryAx in transitive closure → bisect + rollback). That
fires only when ALL workspace roots are proved — in a multi-problem
workspace, an unproved sibling root blocks the gate indefinitely, so
the sorryAx slips through and survives until someone manually checks.

`assembly_gate` is the parse-time replacement: scan the strategy patch
body for any literal `sorry` token after stripping comments. Combined
with the existing per-file verify_file pass (which catches actual
elaboration errors), this guarantees that by the time a Backward
strategy reaches `ready_for_verify`, its body is sorry-free AND
elaborates cleanly. promote_to_alias's mechanical trust becomes earned.
"""
from __future__ import annotations

import re
from pathlib import Path


_SORRY_RE = re.compile(r"\bsorry\b")


def strip_lean_comments(text: str) -> str:
    """Remove Lean 4 comments so a `sorry` inside a comment doesn't
    trigger the assembly gate.

    Handles:
      - `-- single-line comment\n`
      - `/- block comment -/` (non-nested; nested blocks are uncommon
        in strategy patches and not worth a full parser)
      - `/-- doc comment -/` (treated like a block comment)

    Strings are NOT preserved — they're rare in proof scripts and the
    `sorry` keyword in a string would still be suspicious. If this
    becomes false-positive in practice, switch to a Lean parser.
    """
    # Block comments first (greedy across newlines), then line comments.
    out = re.sub(r"/-.*?-/", "", text, flags=re.DOTALL)
    out = re.sub(r"--[^\n]*", "", out)
    return out


def assembly_gate_check_sorry(strategy_path: Path) -> tuple[bool, str]:
    """Return (ok, message). `ok=True` iff the strategy file's body
    (post-comment-strip) contains no `sorry` token.

    The strategy file at this point already has framework-injected
    imports (`_inject_imports_for_subs`) plus the agent's namespace +
    `theorem s<id> ... := by <body>` block. Sorry in the body means the
    agent left a placeholder; sorry in a comment is fine.
    """
    try:
        text = strategy_path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"cannot read {strategy_path}: {exc}"
    stripped = strip_lean_comments(text)
    if _SORRY_RE.search(stripped):
        return False, (
            f"{strategy_path.name}: body contains literal `sorry` — "
            f"Backward agent must replace every `have h_<slug> := by sorry` "
            f"placeholder with a real sub-goal reference "
            f"`have h_<slug> := <slug> <args>` before submitting"
        )
    return True, "ok"
