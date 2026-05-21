import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_slope_tendsto_q_at_zero

namespace Problems.residue_thm

-- Bridge HasDerivAt at z via `hasDerivAt_iff_tendsto_slope_zero`: the slope
-- `t⁻¹ • (F (z + t) - F z)` agrees with the segment-average `∫ Q (z + t' · t)`
-- on a punctured ball (via h_seg, dividing by t), and the average tends to Q z
-- (h_avg); the algebraic-bridge sub-goal packages this congr' + filter restrict.
theorem s10550
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ} (z : ℂ)
    (hzne : z ≠ a)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h)
    (h_avg : Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z))) :
    HasDerivAt F (Q z) z  := by
  have h_slope := slope_tendsto_q_at_zero z hzne h_seg h_avg
  exact hasDerivAt_iff_tendsto_slope_zero.mpr h_slope

end Problems.residue_thm
