-- Pointwise analyticity via a local fixed-radius substitution.
-- At each z₁ ∈ ball z₀ R, set r₁ := (dist z₁ z₀ + R) / 2.
-- Sub-goal `cauchy_integral_fixed_radius_analytic_on`: fixed-radius Cauchy integral
-- is analytic on `ball z₀ r₁` (standard `hasFPowerSeriesOn_cauchy_integral`).
-- Sub-goal `outer_g_local_radius_equality`: near z₁, the variable-radius integrand
-- agrees with the fixed-radius one (radius-independence on the two-puncture annulus).
-- Combinator: `AnalyticOn.analyticAt` on the fixed-radius lemma + `AnalyticAt.congr`
-- with the eventual equality, then `AnalyticAt.analyticWithinAt` to land in `AnalyticOn`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10416

namespace Problems.residue_thm

def outer_g_canonical_analytic_on_ball := @Problems.residue_thm.s10416

end Problems.residue_thm
