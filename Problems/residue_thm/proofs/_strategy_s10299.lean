import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_eq_two_radii

namespace Problems.residue_thm

-- Decompose by isolating the contour-integral bridge from the residue unfold.
-- One sub-goal: equality of circle integrals at two radii valid for two
-- possibly-different analytic radii — Builder chains the sibling lemma twice
-- via a small auxiliary radius ρ ≤ min r (Classical.choose hex / 2).
-- The combinator builds the existence proof from `hf`, unfolds `Complex.residue`
-- via `dif_pos hex`, peels the `(1/(2πi)) *` factor, and applies the bridge with
-- the analyticity provided by `Classical.choose_spec hex` on one side and `hf` on
-- the other.
theorem s10299
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r : ℝ} (hr : 0 < r) (hrR : r < R) :
    Complex.residue f z₀ =
      (1 / (2 * Real.pi * Complex.I)) * ∮ z in C(z₀, r), f z  := by
  have hex : ∃ R' : ℝ, 0 < R' ∧ AnalyticOn ℂ f (Metric.ball z₀ R' \ {z₀}) :=
    ⟨R, lt_trans hr hrR, hf⟩
  obtain ⟨hR'_pos, hf'⟩ := Classical.choose_spec hex
  have h_bridge : (∮ z in C(z₀, Classical.choose hex / 2), f z) = (∮ z in C(z₀, r), f z) :=
    circle_integral_eq_two_radii hf' hf (half_pos hR'_pos) (half_lt_self hR'_pos) hr hrR
  unfold Complex.residue
  rw [dif_pos hex, h_bridge]

end Problems.residue_thm
