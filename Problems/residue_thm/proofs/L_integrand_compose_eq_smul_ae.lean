-- Decomposition: reduce the a.e. chain-rule equation to the bare pointwise chain rule
-- `deriv (γ ∘ φ) t = deriv φ t • deriv γ (φ t)` a.e. on Ioc 0 1.
-- After the substitution, `mul_smul_comm` rebalances the scalar across the product with `Q`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10611

namespace Problems.residue_thm

def integrand_compose_eq_smul_ae := @Problems.residue_thm.s10611

end Problems.residue_thm
