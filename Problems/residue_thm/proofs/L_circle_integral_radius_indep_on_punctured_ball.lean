-- Apply `Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable` with `s = ∅`.
-- Sub-goal 1 supplies continuity on the closed annulus `r₁ ≤ ‖z - z₀‖ ≤ r₂`.
-- Sub-goal 2 supplies pointwise differentiability on the open interior.
-- Both follow because the annulus sits inside `ball z₀ R \ {z₀}` where `hf` provides
-- analyticity; each sub-goal drops one of the contour-integral hypotheses, so both are
-- strictly simpler than the parent equality of integrals.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10298

namespace Problems.residue_thm

def circle_integral_radius_indep_on_punctured_ball := @Problems.residue_thm.s10298

end Problems.residue_thm
