# cantor_xi_measure — BRIEF

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
Standard 4-step measure-theory argument:

1. **Each iterate has measure `(1−ξ)^n`.** Induct on `n`. Base: `volume (Icc 0 1) = 1`.
   Step: `cantorXi ξ (n+1)` is the disjoint union of two affine images of
   `cantorXi ξ n`, each scaled by `(1-ξ)/2`. So `volume (cantorXi ξ (n+1)) =
   2 · ((1-ξ)/2) · volume (cantorXi ξ n) = (1-ξ) · volume (cantorXi ξ n)`.
   The two images are disjoint because the right piece sits in `[(1+ξ)/2, 1]`
   and the left piece in `[0, (1-ξ)/2]`, separated by the gap `((1-ξ)/2, (1+ξ)/2)`.

2. **The Cantor set is contained in every iterate.** `cantorSet ξ ⊆ cantorXi ξ n`
   follows directly from the definition `cantorSet ξ = ⋂ n, cantorXi ξ n`.

3. **Measure inequality for all `n`.** From (1) and (2): `volume (cantorSet ξ)
   ≤ (1-ξ)^n` for every `n : ℕ`.

4. **Take the limit.** `0 < ξ < 1` gives `0 ≤ 1-ξ < 1`, so `(1-ξ)^n → 0`.
   A non-negative quantity bounded above by something tending to 0 is 0.

The disjointness in step 1 needs the `0 < ξ` hypothesis (otherwise the two
images overlap). The bound `1 - ξ < 1` is needed in step 4. Both endpoints
of the open interval `0 < ξ < 1` are essential.
