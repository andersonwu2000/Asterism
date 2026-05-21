-- Strip the g, P, hg_eq, hP_eq layer by choosing concrete radii
-- `r := (dist z z₀ + R)/2` (so `dist z z₀ < r < R`) and `ε := dist z z₀ / 2`
-- (so `0 < ε < dist z z₀ < R`). The single sub-goal `annulus_residue_diff`
-- supplies the annular residue identity `(∮ outer f(w)/(w-z)) - (∮ inner f(w)/(w-z))
-- = 2πi · f(z)`; combining with `hg_eq`, `hP_eq` reduces `f z = g z + P z`
-- to a `field_simp`/`ring` arithmetic step.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10410

namespace Problems.residue_thm

def cauchy_annulus_sum_formula := @Problems.residue_thm.s10410

end Problems.residue_thm
