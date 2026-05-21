-- Define P(z) using the canonical radius ε_c(z) = min R (dist z z₀) / 2; for
-- z ≠ z₀ this lies strictly between 0 and both R and dist z z₀, so it is a
-- valid integration radius. The sub-goal `integrand_radius_indep` (radius
-- independence of `∮ f w / (w - z) dw` over valid radii) then equates the
-- canonical integral with the integral at any other valid ε, closing the
-- existential equation. The sub-goal drops the outer ∃ binder and reduces the
-- witness construction to a pure equality between two circle integrals.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10415

namespace Problems.residue_thm

def inner_part_value_witness := @Problems.residue_thm.s10415

end Problems.residue_thm
