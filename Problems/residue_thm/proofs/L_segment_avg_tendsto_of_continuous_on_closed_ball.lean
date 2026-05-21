-- Split tendsto-to-Q(z) into (value at h=0) + (ContinuousAt at 0):
-- (1) `integral_segment_zero` — Builder: at h=0 the integrand collapses
--     (t·0=0, z+0=z) so ∫₀¹ Q z dt = Q z by `intervalIntegral.integral_const`.
-- (2) `continuousAt_segment_integral_of_continuous_on_closed_ball` — Backward:
--     the parametric integral is continuous at h=0. With Q ContinuousOn a closed
--     ball around z, for ‖h‖ ≤ R the segment t↦z+t·h stays in the ball, giving
--     AEStronglyMeasurable + bound for DCT (`continuousAt_of_dominated_interval`,
--     lesson 30 pattern).
-- Combinator: ContinuousAt unfolds to Tendsto to value-at-0; rewrite via (1).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10643

namespace Problems.residue_thm

def segment_avg_tendsto_of_continuous_on_closed_ball := @Problems.residue_thm.s10643

end Problems.residue_thm
