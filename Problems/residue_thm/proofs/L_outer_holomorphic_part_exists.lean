-- Outer holomorphic part `g(z) := (2πi)⁻¹ * ∮_{C(z₀, (dist z z₀ + R)/2)} f(w)/(w-z) dw`,
-- a canonical radius midway between `dist z z₀` and `R`. Two sub-goals:
--   * outer_g_canonical_analytic_on_ball: analyticity on `ball z₀ R` via locally agreeing
--     with the fixed-radius Cauchy integral (analytic by `hasFPowerSeriesOn_cauchy_integral`).
--   * outer_g_canonical_eq_at_radius: the formula at any other radius `r ∈ (dist z z₀, R)`
--     follows from radius-independence on the annulus where `w ↦ f(w)/(w-z)` is analytic.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10411

namespace Problems.residue_thm

def outer_holomorphic_part_exists := @Problems.residue_thm.s10411

end Problems.residue_thm
