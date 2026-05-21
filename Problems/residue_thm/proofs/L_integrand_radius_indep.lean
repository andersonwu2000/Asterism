-- Reduce radius independence of `∮ f w / (w - z)` to `circle_integral_eq_two_radii`
-- on the integrand `g w = f w / (w - z)`, using `ρ := min R (dist z z₀)` as a
-- common analyticity radius. The single sub-goal supplies
-- `AnalyticOn ℂ g (ball z₀ ρ \ {z₀})`; `ε₁, ε₂ < ρ` is pure `lt_min`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10421

namespace Problems.residue_thm

def integrand_radius_indep := @Problems.residue_thm.s10421

end Problems.residue_thm
