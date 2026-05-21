-- Decompose into the pointwise statement: each pole a ∈ T has a positive
-- radius r whose punctured ball lies in U \ T, hence f is analytic there.
-- Assemble into a global function r : ℂ → ℝ via Classical.choose / dif_pos.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10323

namespace Problems.residue_thm

def exists_outer_radii_analyticity := @Problems.residue_thm.s10323

end Problems.residue_thm
