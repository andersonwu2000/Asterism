-- Direct chain rule at endpoint 0: deriv φ 0 = 0 forces (γ∘φ)' = (deriv φ 0) • γ' = 0.
-- Builds HasDerivWithinAt for φ (from HasDerivAt via C¹) and γ at φ 0 ∈ Icc (from C¹ on Icc),
-- composes via HasDerivWithinAt.scomp, then promotes to derivWithin via uniqueDiffOn_Icc.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10610

namespace Problems.residue_thm

def gamma_circ_phi_derivwithin_zero_at_zero := @Problems.residue_thm.s10610

end Problems.residue_thm
