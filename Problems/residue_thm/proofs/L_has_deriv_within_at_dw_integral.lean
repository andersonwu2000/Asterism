-- FTC for `∫₀ˢ derivWithin γ (Icc 0 1) t / (γ t - a)` with derivative value
-- `derivWithin γ (Icc 0 1) s / (γ s - a)`. Sub-goal `dw_integrand_continuous_on`
-- (Builder): continuity of the integrand on `Icc 0 1` — drives both the integrability
-- and the pointwise FTC derivative-value via `integral_hasDerivWithinAt_right` under
-- the canonical `FTCFilter` instance on `nhdsWithin (Icc 0 1)`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10314

namespace Problems.residue_thm

def has_deriv_within_at_dw_integral := @Problems.residue_thm.s10314

end Problems.residue_thm
