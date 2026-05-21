-- Switch `deriv γ` for `derivWithin γ (Icc 0 1)` inside the integrand. They agree
-- on `Ioo 0 1` (i.e. a.e. on the integration interval), so the integrals coincide,
-- but `derivWithin γ (Icc 0 1)` is cleanly continuous on `Icc 0 1` via
-- `ContDiffOn.continuousOn_derivWithin` — unlike `deriv γ`, which can carry junk
-- values at endpoints when `γ` is only `ContDiffOn` rather than globally `ContDiff`.
-- Sub-goal 1 (`integral_eq_integral_deriv_within`): pointwise integral equality on
-- `Icc 0 1` (a.e.-equal integrands → `intervalIntegral.integral_congr_ae`).
-- Sub-goal 2 (`differentiable_integral_deriv_within`): FTC differentiability of the
-- `derivWithin`-integrand antiderivative. Closer transfers via `DifferentiableOn.congr`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10306

namespace Problems.residue_thm

def differentiable_integral_path := @Problems.residue_thm.s10306

end Problems.residue_thm
