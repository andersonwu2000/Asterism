-- Direct application of `Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable`
-- with the closed annulus `closedBall z₀ r₂ \ ball z₀ r₁` contained in the punctured ball
-- `ball z₀ R \ {z₀}`. AnalyticOn → ContinuousOn (annulus) and DifferentiableAt (open annulus).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10277

namespace Problems.residue_thm

def circle_integral_eq_of_le_radii := @Problems.residue_thm.s10277

end Problems.residue_thm
