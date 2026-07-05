-- ∂∘∂ = 0 of the currents complex: leaf-bypass, no sub-goals.
-- Unfold both `boundary`s to (T.comp (extDerivCLM (k+1))).comp (extDerivCLM k),
-- reassociate via comp_assoc, rewrite the inner d∘d to 0 via the Library's
-- extDerivCLM_comp_extDerivCLM_eq_zero, then comp_zero closes T.comp 0 = 0.
import Mathlib
import Problems.Geometry.currents_boundary_zero.Defs
import Problems.Geometry.currents_boundary_zero.proofs._strategy_s17779

namespace Problems.Geometry.currents_boundary_zero

def main := @Problems.Geometry.currents_boundary_zero.s17779

end Problems.Geometry.currents_boundary_zero
