import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_hasderivat_from_avg_seg_inlined
import Problems.residue_thm.proofs.L_q_segment_avg_tendsto_punctured

namespace Problems.residue_thm

-- Bridge HasDerivAt at z via the average-tendsto pattern (proven in s10550):
-- (1) `q_segment_avg_tendsto_punctured` — from ContinuousOn Q on punctured set,
--     produce h_avg : Tendsto of the segment-average integral to Q z. The
--     punctured hypothesis is exactly enough to make `t ↦ Q (z + t·h)` continuous
--     on [0,1] for ‖h‖ < dist z a (segment stays in the punctured set), hence
--     AEStronglyMeasurable — the gap ContinuousAt-only decompositions hit.
-- (2) `hasderivat_from_avg_seg_inlined` — Builder wrapper for the proved bridge
--     `hasderivat_from_avg_tendsto_and_segment` (s10550); takes hzne + h_seg +
--     h_avg → HasDerivAt. Wrapper needed because proved-sibling slugs are not
--     auto-imported into a Backward `patch.lean` (lesson 1).
theorem s10629
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont_on : ContinuousOn Q (Set.univ \ ({a} : Set ℂ)))
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    HasDerivAt F (Q z) z  := by
  have hzne : z ≠ a := by intro h; exact hz.2 (Set.mem_singleton_iff.mpr h)
  have h_avg := q_segment_avg_tendsto_punctured z hz h_cont_on
  exact hasderivat_from_avg_seg_inlined z hzne h_seg h_avg

end Problems.residue_thm
