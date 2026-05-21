-- Reduce `Function.Injective W'` to a single covering-space lemma:
-- after `Quotient.ind` exposes loop representatives `γa, γb`, the chain
-- `W' ⟦γa⟧ = W' ⟦γb⟧ → (W' ⟦γa⟧ : ℝ) * (2π) = (W' ⟦γb⟧ : ℝ) * (2π)
--  → Γa(1) = Γb(1)` (via `h_char`) leaves only `lift_endpoint_eq_imp_quot_eq`
-- (converse of `lift_endpoint_eq_of_homotopic`) to finish. That sub-goal
-- holds because the universal cover ℝ → Circle has simply-connected total
-- space, so equal lifted endpoints give a homotopy in ℝ that pushes down.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10695

namespace Problems.pi1_circle

def winding_quot_injective := @Problems.pi1_circle.s10695

end Problems.pi1_circle
