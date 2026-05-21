-- Reduce quotient equality to path-homotopy: ⟦γa⟧ = ⟦γb⟧ in the homotopy
-- quotient holds iff `γa.Homotopic γb`. The sub-goal carries the universal
-- cover argument (ℝ simply-connected + push-down via Circle.exp), and
-- `Quotient.sound` lifts the path-level homotopy to the quotient level.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10697

namespace Problems.pi1_circle

def lift_endpoint_eq_imp_quot_eq := @Problems.pi1_circle.s10697

end Problems.pi1_circle
