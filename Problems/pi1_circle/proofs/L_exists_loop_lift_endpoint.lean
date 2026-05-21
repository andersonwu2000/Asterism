-- Construct the standard loop γ_n with companion real lift Γ_n satisfying
-- `Circle.exp ∘ Γ_n = γ_n.toContinuousMap`, `Γ_n 0 = 0`, `Γ_n 1 = n*(2π)`.
-- The canonical lift then equals Γ_n by `eq_liftPath_iff'`, giving the
-- endpoint conclusion immediately.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10698

namespace Problems.pi1_circle

def exists_loop_lift_endpoint := @Problems.pi1_circle.s10698

end Problems.pi1_circle
