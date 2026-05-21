-- Define W γ := Classical.choose (lift_endpoint_mem_two_pi_int γ) and lift it
-- to Path.Homotopic.Quotient via Quotient.lift. The only non-trivial input is
-- homotopy invariance of the chosen integer (sub-goal). The characterizing
-- equation Γ γ 1 = (W'⟦γ⟧ : ℝ) * (2π) then reduces to Classical.choose_spec.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10692

namespace Problems.pi1_circle

def winding_quot_function_char := @Problems.pi1_circle.s10692

end Problems.pi1_circle
