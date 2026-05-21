import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_kernel_cont_on_annulus
import Problems.residue_thm.proofs.L_cauchy_kernel_diff_at_open_annulus

namespace Problems.residue_thm

-- Radius-independence of `∮ w in C(z₀, r), f w / (w - z')` reduces to Mathlib's
-- `circleIntegral_eq_of_differentiable_on_annulus_off_countable` after WLOG `r₁ ≤ r₂`.
-- Two sub-goals supply the annulus-side hypotheses of that lemma for the Cauchy kernel
-- `w ↦ f w / (w - z')`: continuity on the closed annulus, and differentiability at each
-- point of the open annulus. Both isolate the "kernel has no pole inside the annulus"
-- analytic reasoning into Builder leaves and keep the patch as pure case-dispatch.
theorem s10422
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z' ∈ Metric.ball z₀ R, ∀ r₁ r₂ : ℝ,
      dist z' z₀ < r₁ → r₁ < R → dist z' z₀ < r₂ → r₂ < R →
      (∮ w in C(z₀, r₁), f w / (w - z')) = (∮ w in C(z₀, r₂), f w / (w - z'))  := by
  intro z' hz' r₁ r₂ hd₁ hr₁R hd₂ hr₂R
  have hr₁p : 0 < r₁ := lt_of_le_of_lt dist_nonneg hd₁
  have hr₂p : 0 < r₂ := lt_of_le_of_lt dist_nonneg hd₂
  have h_cont := cauchy_kernel_cont_on_annulus hR hf
  have h_diff := cauchy_kernel_diff_at_open_annulus hR hf
  rcases le_total r₁ r₂ with hle | hle
  · have h_c := h_cont z' hz' r₁ r₂ hd₁ hle hr₂R
    have h_d := h_diff z' hz' r₁ r₂ hd₁ hle hr₂R
    exact (Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable hr₁p hle
      Set.countable_empty h_c (fun z hz => h_d z hz.1)).symm
  · have h_c := h_cont z' hz' r₂ r₁ hd₂ hle hr₁R
    have h_d := h_diff z' hz' r₂ r₁ hd₂ hle hr₁R
    exact Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable hr₂p hle
      Set.countable_empty h_c (fun z hz => h_d z hz.1)

end Problems.residue_thm

