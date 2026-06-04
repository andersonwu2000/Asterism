# inner_zero_iff_smul — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the strategy skeleton's body — signature locked). See the kind-specific prompt for layout.

## Strategic notes (from Manifest.md)
Two directions, both via expanding `‖x ± αy‖² = ‖x‖² ± 2α·⟨x,y⟩ + α²‖y‖²`:

- **Forward** `⟨x,y⟩ = 0 → ∀α, ‖x+αy‖ = ‖x-αy‖`. Substitute `⟨x,y⟩=0` into
  the squared-norm expansion; the `±2α·⟨x,y⟩` term vanishes, leaving the
  same expression on both sides. Take square roots (norms are non-negative).

- **Reverse** `(∀α, ‖x+αy‖ = ‖x-αy‖) → ⟨x,y⟩ = 0`. Pick a specific α to
  force the `4α·⟨x,y⟩` cross term to zero. The trick: `α := ⟨x,y⟩` (or
  `α := 1` works in real inner product since `⟨x,y⟩ ∈ ℝ` already). Equal
  squared norms then give `α · ⟨x,y⟩ = 0`, which combined with the choice
  of `α` yields `⟨x,y⟩ = 0` directly.

The "for all α" universal makes this strictly more general than the
single-α Pythagorean identity Mathlib has — don't try to look up an
existing iff with this exact shape; build it from the squared-norm
expansion.
