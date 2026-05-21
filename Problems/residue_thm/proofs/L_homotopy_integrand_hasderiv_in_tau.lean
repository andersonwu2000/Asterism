-- Split the τ-derivative of the integrand at fixed t into chain-rule and
-- partial-derivative components, combined via the product rule. Both
-- sub-goals use t ∈ Ioo 0 1 to dodge `deriv (H τ) t` endpoint-junk.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10336

namespace Problems.residue_thm

def homotopy_integrand_hasderiv_in_tau := @Problems.residue_thm.s10336

end Problems.residue_thm
