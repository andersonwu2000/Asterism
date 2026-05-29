-- The radius-1/2 sphere in ℝ³ is uncountable: it is preconnected (dim > 1, via
-- `isConnected_sphere`) and contains two distinct points, and a preconnected set
-- with two distinct points in a metric space is uncountable.
-- Sub-goals: (1) general topology lemma `preconnected_two_points_uncountable`
-- (abstract, no sphere geometry); (2) `half_sphere_two_distinct` (two explicit
-- antipodal points on the radius-1/2 sphere). Preconnectedness is cited inline.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11521

namespace Problems.Geometry.banach_tarski

def half_sphere_uncountable := @Problems.Geometry.banach_tarski.s11521

end Problems.Geometry.banach_tarski
