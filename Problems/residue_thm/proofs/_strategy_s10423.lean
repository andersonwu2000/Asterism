import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_norm_le_decay_eventually
import Problems.residue_thm.proofs.L_tendsto_const_div_dist_zero

namespace Problems.residue_thm

-- Squeeze: the circle integral's norm is eventually bounded by M / (‖z - z₀‖ - R/2)
-- (analytic estimate via uniform bound on f over the sphere; sub-goal 1), and
-- that bound tends to 0 at cocompact ℂ (asymptotic, sub-goal 2).
-- Combine via tendsto_zero_iff_norm_tendsto_zero + squeeze_zero'.
theorem s10423
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    Filter.Tendsto
      (fun z => ∮ w in C(z₀, R/2), f w / (w - z))
      (Filter.cocompact ℂ) (nhds 0)  := by
  have h1 := circle_integral_norm_le_decay_eventually hR hf P hP
  have h2 := tendsto_const_div_dist_zero hR hf P hP
  obtain ⟨M, _hM0, hMevent⟩ := h1
  refine (tendsto_zero_iff_norm_tendsto_zero).mpr ?_
  refine squeeze_zero' (Filter.Eventually.of_forall (fun z => norm_nonneg _)) hMevent (h2 M)

end Problems.residue_thm
