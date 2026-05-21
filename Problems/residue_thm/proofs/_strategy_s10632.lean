import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_seg_f_comp_continuous
import Problems.residue_thm.proofs.L_seg_f_comp_hasderivat_ioo
import Problems.residue_thm.proofs.L_seg_integrand_integrable

namespace Problems.residue_thm

-- Specialize Mathlib's `intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le`
-- to the segment integrand. Three Builder sub-goals supply the FTC ingredients
-- for the composite `F ∘ (t ↦ z + t·(w-z))` on `Icc 0 1`:
-- (1) `seg_f_comp_continuous` — continuity on the closed interval,
-- (2) `seg_f_comp_hasderivat_ioo` — chain rule on the open interior
--     (uses `Icc 0 1 ∈ 𝓝 t` for `t ∈ Ioo 0 1`, sidestepping the boundary trap),
-- (3) `seg_integrand_integrable` — IntervalIntegrable of the integrand.
-- Combinator: feed to `integral_eq_sub_of_hasDerivAt_of_le` and collapse
-- endpoints `z + 0·(w-z) ↦ z`, `z + 1·(w-z) ↦ w` via `push_cast; ring`.
theorem s10632
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    (∫ t in (0:ℝ)..1, f (z + (t:ℂ) * (w - z)) * (w - z)) = F w - F z  := by
  have h_cont := seg_f_comp_continuous hF hz hw
  have h_deriv := seg_f_comp_hasderivat_ioo hF hz hw
  have h_int := seg_integrand_integrable hF hz hw
  have h_ftc := intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le
    (a := 0) (b := 1) zero_le_one h_cont h_deriv h_int
  have h0 : z + ((0:ℝ):ℂ) * (w - z) = z := by push_cast; ring
  have h1 : z + ((1:ℝ):ℂ) * (w - z) = w := by push_cast; ring
  rw [h0, h1] at h_ftc
  exact h_ftc

end Problems.residue_thm
