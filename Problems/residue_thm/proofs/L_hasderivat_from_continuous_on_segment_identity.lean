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
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10629

namespace Problems.residue_thm

def hasderivat_from_continuous_on_segment_identity := @Problems.residue_thm.s10629

end Problems.residue_thm
