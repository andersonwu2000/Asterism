-- Product+chain rule for τ-derivWithin: combine a HasDerivWithinAt chain rule on
-- (τ' ↦ f (H τ' t)) with τ-side DifferentiableWithinAt of (τ' ↦ deriv (H τ') t),
-- then apply `HasDerivWithinAt.mul` and `.derivWithin` over `uniqueDiffOn_Icc_zero_one`.
-- Residue between the .mul output `(c' · d) * b + c · d'` and the goal's
-- `c · b · c' + c · d'` is a pure ring permutation handled by `linear_combination`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10345

namespace Problems.residue_thm

def derivwithin_section_product_chain_eq := @Problems.residue_thm.s10345

end Problems.residue_thm
