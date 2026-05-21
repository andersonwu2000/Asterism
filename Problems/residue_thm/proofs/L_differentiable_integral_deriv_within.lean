-- Reduce FTC differentiability of the `derivWithin`-integrand antiderivative to
-- (1) continuity of the integrand on `Icc 0 1` and (2) a generic FTC primitive lemma.
-- Sub-goal `continuous_on_integrand`: compose `ContDiffOn.continuousOn_derivWithin`
-- (γ' is continuous on `Icc 0 1`) with continuity of `γ t - a` (from `hγ.continuousOn.sub`)
-- and `havoid`-driven non-vanishing of the denominator.
-- Sub-goal `differentiable_on_integral_of_continuous_on`: abstract — for any continuous
-- `f` on `Icc 0 1`, the antiderivative `s ↦ ∫₀^s f` is `DifferentiableOn ℝ` on `Icc 0 1`
-- (FTC composition via `intervalIntegral.integral_hasDerivWithinAt_right` and `_left`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10310

namespace Problems.residue_thm

def differentiable_integral_deriv_within := @Problems.residue_thm.s10310

end Problems.residue_thm
