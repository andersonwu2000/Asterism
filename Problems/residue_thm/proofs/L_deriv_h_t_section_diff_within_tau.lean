-- Rewrite `deriv (H τ') t` pointwise to `fderivWithin G (Icc×Icc) (τ', t) (0,1)` on
-- τ' ∈ Icc 0 1 (sub-goal 1, chain rule via slice map + `Icc ∈ nhds t` for interior t),
-- then transfer DifferentiableWithinAt in τ from the fderivWithin form (sub-goal 2,
-- `ContDiffOn.fderivWithin` ↑ slice-map composition) via `DifferentiableWithinAt.congr`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10352

namespace Problems.residue_thm

def deriv_h_t_section_diff_within_tau := @Problems.residue_thm.s10352

end Problems.residue_thm
