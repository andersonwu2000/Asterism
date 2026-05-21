-- FTC for `∫₀ˢ deriv γ t / (γ t - a)` with derivative value
-- `derivWithin γ (Icc 0 1) s / (γ s - a)`. Direct FTC fails because `deriv γ` is junk at
-- endpoints (Icc 0 1 ∉ nhds 0/1), so the integrand is not continuous on Icc; swap to the
-- `derivWithin`-integrand which IS continuous on Icc, apply FTC there, then transfer.
-- Sub-goal `has_deriv_within_at_dw_integral` (Backward): FTC for the derivWithin version.
-- Sub-goal `integral_eq_integral_deriv_within` (Builder): integrals agree pointwise on
-- Icc 0 1 (integrands differ only at endpoints, a measure-zero set).
-- Combinator: `HasDerivWithinAt.congr` swaps the integrand-function side.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10313

namespace Problems.residue_thm

def h_deriv_integral_dw := @Problems.residue_thm.s10313

end Problems.residue_thm
