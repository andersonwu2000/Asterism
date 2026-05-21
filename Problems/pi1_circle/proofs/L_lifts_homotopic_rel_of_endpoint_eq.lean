-- Reduce HomotopicRel-of-lifts to the general fact that any two continuous maps
-- I → ℝ with matching endpoints are HomotopicRel {0,1} (ℝ is contractible).
-- Sub-goal `real_paths_homotopic_rel_of_endpoints_eq` packages this; we feed it
-- the two liftPaths after rewriting the source endpoints via `liftPath_zero`.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10701

namespace Problems.pi1_circle

def lifts_homotopic_rel_of_endpoint_eq := @Problems.pi1_circle.s10701

end Problems.pi1_circle
