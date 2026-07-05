-- Package the integration current as a continuous dual via the LF universal property.
-- One real sub-goal: per-compact CLM `T_K` with explicit value (`pullback_per_k_clm_exists`);
-- glue them through `TestFunction.limitCLM`; the agreement clause is `rfl` (limitCLM coercion).
import Mathlib
import Problems.Geometry.integration_current_clm.Defs
import Problems.Geometry.integration_current_clm.proofs._strategy_s17844

namespace Problems.Geometry.integration_current_clm

def main := @Problems.Geometry.integration_current_clm.s17844

end Problems.Geometry.integration_current_clm
