import Mathlib
import Problems.Minif2f.algebra_manipexpr_2erprsqpesqeqnrpnesq.Defs

namespace Problems.Minif2f.algebra_manipexpr_2erprsqpesqeqnrpnesq

-- Pure ring identity: (-r + -e)^2 = r^2 + 2*r*e + e^2 = 2*(e*r) + (e^2 + r^2)
theorem s555 : ∀ (e r : ℂ), 2 * (e * r) + (e ^ 2 + r ^ 2) = (-r + -e) ^ 2  := by
  intro e r
  ring

end Problems.Minif2f.algebra_manipexpr_2erprsqpesqeqnrpnesq
