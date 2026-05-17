---
problem: residue_thm
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# residue_thm — Cauchy residue theorem for a single isolated pole

## Statement
∀ {f : ℂ → ℂ} {z₀ : ℂ} {r : ℝ},
  0 < r →
  AnalyticOn ℂ f (Metric.ball z₀ r \ {z₀}) →
  (∮ z in circle z₀ r, f z) = 2 * Real.pi * Complex.I *
    Complex.residue f z₀

## Lemma hints
- `Mathlib.Analysis.Complex.CauchyIntegral` — Cauchy integral formula on
  a disk; ground truth for the punctured-disk case via deformation.
- `Mathlib.Analysis.Complex.Polynomial` — `circleIntegral` API, the
  parametrisation `∮ z in circle z₀ r, f z`.
- `Complex.residue` (if/once Mathlib lands it) — formal Laurent
  coefficient `a₋₁`. Phase 2 likely requires Forward to introduce this
  definition (or a constructive surrogate) if Mathlib does not provide it.
- `AnalyticAt.removable_singularity_iff` — bridges the punctured-disk
  hypothesis to a removable / pole classification.

## Strategic notes
The classical proof decomposes naturally:

1. **Laurent expansion at z₀**. Under analyticity on the punctured disk,
   `f` has a Laurent series. The coefficient `a₋₁` is the residue by
   definition.

2. **Term-by-term integration over the circle**. For `k ≠ -1`,
   `∮ z in circle z₀ r, (z − z₀)^k = 0` (antiderivative exists in the
   annulus). The `k = -1` term gives `2πi`.

3. **Swap sum and integral**. Uniform convergence of the Laurent series
   on `circle z₀ r` justifies the interchange.

Strategist-level expectations (Phase 2 validation target):
- T1 routine sees Backward stuck on step 2 (missing named lemma for
  `circleIntegral (z - z₀)^k = 0 when k ≠ -1`) → Inject(Forward) to
  produce that lemma.
- A second Forward injection may be needed for the swap-sum step.
- If Mathlib's `Complex.residue` is unavailable, Strategist issues
  `RequestUserAmend(file="Defs.lean")` to introduce a working
  definition.

This problem is deliberately sitting at the Mathlib edge: Cauchy's
integral formula is in, but several named lemmas around residues are
not, so Forward has work to do. Refine the statement / hints as
Mathlib evolves.
