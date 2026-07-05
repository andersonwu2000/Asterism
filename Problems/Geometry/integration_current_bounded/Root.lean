-- Bound `DiffForm.integral (pullbackFlatForm e ψ)` by `C * M` via the FINITE
-- subordinate `SmoothBumpCovering` that `DiffForm.integral` sums over.
-- Choose a subordinate covering `B` (exists_isSubordinate), extract a uniform
-- chart-derivative bound `D` over its finite index (`finite_cover_deriv_bound`),
-- then `finsum_assembly` produces the witness `C` and the per-`ψ` estimate.
import Mathlib
import Problems.Geometry.integration_current_bounded.Defs
import Problems.Geometry.integration_current_bounded.proofs._strategy_s17832

namespace Problems.Geometry.integration_current_bounded

def main := @Problems.Geometry.integration_current_bounded.s17832

end Problems.Geometry.integration_current_bounded
