-- Reduce to the ordered-radius case `r₁ ≤ r₂` via `le_total`. The single
-- sub-lemma `circle_integral_eq_of_le_radii` handles the ordered case via
-- Mathlib's `circleIntegral_eq_of_differentiable_on_annulus_off_countable`
-- on the closed annulus, which sits inside the punctured ball where `f` is
-- analytic.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10276

namespace Problems.residue_thm

def circle_integral_radius_independence := @Problems.residue_thm.s10276

end Problems.residue_thm
