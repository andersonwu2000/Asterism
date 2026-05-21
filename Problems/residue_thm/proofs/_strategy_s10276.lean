import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_eq_of_le_radii

namespace Problems.residue_thm

-- Reduce to the ordered-radius case `r₁ ≤ r₂` via `le_total`. The single
-- sub-lemma `circle_integral_eq_of_le_radii` handles the ordered case via
-- Mathlib's `circleIntegral_eq_of_differentiable_on_annulus_off_countable`
-- on the closed annulus, which sits inside the punctured ball where `f` is
-- analytic.
theorem s10276
    {f : ℂ → ℂ} {z₀ : ℂ} {R r₁ r₂ : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (hr₁ : 0 < r₁) (hr₁R : r₁ < R) (hr₂ : 0 < r₂) (hr₂R : r₂ < R) :
    (∮ z in C(z₀, r₁), f z) = (∮ z in C(z₀, r₂), f z)  := by
  rcases le_total r₁ r₂ with h | h
  · exact circle_integral_eq_of_le_radii hf hr₁ hr₁R hr₂ hr₂R h
  · exact (circle_integral_eq_of_le_radii hf hr₂ hr₂R hr₁ hr₁R h).symm

end Problems.residue_thm

