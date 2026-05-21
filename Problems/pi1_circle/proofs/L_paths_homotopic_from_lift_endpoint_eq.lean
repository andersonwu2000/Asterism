-- Reduce path-homotopy γa ~ γb to ContinuousMap.HomotopicRel of the ℝ-lifts.
-- Sub-goal: lifts in ℝ with matching endpoints are HomotopicRel {0,1} (simply-connectedness).
-- Combinator: push the lift-level homotopy down via Circle.exp using
-- `ContinuousMap.HomotopicRel.comp_continuousMap` and `liftPath_lifts`.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10700

namespace Problems.pi1_circle

def paths_homotopic_from_lift_endpoint_eq := @Problems.pi1_circle.s10700

end Problems.pi1_circle
