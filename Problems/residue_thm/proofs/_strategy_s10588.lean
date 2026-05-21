import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_hasderivat_from_avg_and_seg
import Problems.residue_thm.proofs.L_q_segment_avg_limit

namespace Problems.residue_thm

-- Decompose pointwise `HasDerivAt F (Q z) z` (at `z ≠ a`, given the local
-- segment identity for F) into two strictly simpler pieces:
-- (1) `q_segment_avg_limit` — the segment average `∫₀¹ Q (z + t·h) dt` tends to
--     `Q z` as `h → 0`, from `ContinuousAt Q z` (analytic core, route via
--     uniform smallness of `Q` on the unit segment, the proven sibling angle).
-- (2) `hasderivat_from_avg_and_seg` — algebraic bridge: given the limit and
--     the segment identity, the slope characterization gives `HasDerivAt`.
theorem s10588
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont : ContinuousAt Q z)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    HasDerivAt F (Q z) z  := by
  have hzne : z ≠ a := by simpa using hz.2
  have h_avg := q_segment_avg_limit Q z h_cont
  exact hasderivat_from_avg_and_seg z hzne h_seg h_avg

end Problems.residue_thm
