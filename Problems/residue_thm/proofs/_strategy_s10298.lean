import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_continuous_on_closed_annulus
import Problems.residue_thm.proofs.L_differentiable_at_open_annulus

namespace Problems.residue_thm

-- Apply `Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable` with `s = ∅`.
-- Sub-goal 1 supplies continuity on the closed annulus `r₁ ≤ ‖z - z₀‖ ≤ r₂`.
-- Sub-goal 2 supplies pointwise differentiability on the open interior.
-- Both follow because the annulus sits inside `ball z₀ R \ {z₀}` where `hf` provides
-- analyticity; each sub-goal drops one of the contour-integral hypotheses, so both are
-- strictly simpler than the parent equality of integrals.
theorem s10298
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r₁ r₂ : ℝ} (hr₁ : 0 < r₁) (hle : r₁ ≤ r₂) (hr₂ : r₂ < R) :
    (∮ z in C(z₀, r₁), f z) = (∮ z in C(z₀, r₂), f z)  := by
  have h_cont := continuous_on_closed_annulus hf hr₁ hle hr₂
  have h_diff := differentiable_at_open_annulus hf hr₁ hle hr₂
  exact (Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable hr₁ hle
    Set.countable_empty h_cont (fun z hz => h_diff z hz.1)).symm

end Problems.residue_thm
