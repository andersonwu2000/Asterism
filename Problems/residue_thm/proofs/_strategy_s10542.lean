import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_hasderivat_from_avg_tendsto_and_segment
import Problems.residue_thm.proofs.L_q_segment_avg_tendsto_at_zero

namespace Problems.residue_thm

-- Decompose `HasDerivAt F (Q z) z` (pointwise dispatch at z ≠ a) into
-- (1) the analytic core `q_segment_avg_tendsto_at_zero`: as `h → 0`, the
-- segment average `∫ t in 0..1, Q (z + t·h)` tends to `Q z` (from
-- `ContinuousAt Q z`); and (2) the algebraic bridge
-- `hasderivat_from_avg_tendsto_and_segment`: combining that limit with the
-- segment identity yields the slope characterization of HasDerivAt at z.
theorem s10542
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont : ContinuousAt Q z)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    HasDerivAt F (Q z) z  := by
  have hzne : z ≠ a := by simpa using hz.2
  have h_avg := q_segment_avg_tendsto_at_zero Q z h_cont
  exact hasderivat_from_avg_tendsto_and_segment z hzne h_seg h_avg

end Problems.residue_thm
