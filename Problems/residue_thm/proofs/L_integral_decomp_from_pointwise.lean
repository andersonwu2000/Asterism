-- Apply the pointwise decomposition `hpw` at `γ t` (valid since γ maps into U \ T),
-- multiply by `deriv γ t`, then lift via integration linearity.
-- Sub-goals:
--   (1) `pointwise_integrand_decomp` — the pointwise equality of integrands on Icc 0 1.
--   (2) `g_along_path_intvl_integrable` — integrability of `g ∘ γ * γ'` on [0,1].
--   (3) `principal_along_path_intvl_integrable` — for each `a ∈ T`, integrability of
--       `P a ∘ γ * γ'` on [0,1].
-- Combinator: `intervalIntegral.integral_congr` swaps the integrand on uIcc 0 1, then
-- `intervalIntegral.integral_add` splits the sum, then `intervalIntegral.integral_finsetSum`
-- pushes the Finset.sum out of the integral.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10457

namespace Problems.residue_thm

def integral_decomp_from_pointwise := @Problems.residue_thm.s10457

end Problems.residue_thm
