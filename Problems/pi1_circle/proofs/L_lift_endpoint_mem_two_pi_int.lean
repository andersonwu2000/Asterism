-- Direct closure: the lifted endpoint Γ 1 maps to γ 1 = 1 under Circle.exp
-- (via liftPath_lifts evaluated at 1 + γ.target), and Circle.exp_eq_one then
-- converts that to the desired ∃ n : ℤ, Γ 1 = n * (2 * π).
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10687

namespace Problems.pi1_circle

def lift_endpoint_mem_two_pi_int := @Problems.pi1_circle.s10687

end Problems.pi1_circle
