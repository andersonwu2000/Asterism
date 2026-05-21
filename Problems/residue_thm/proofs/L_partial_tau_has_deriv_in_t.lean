-- Schwarz mixed-partial via fderivWithin reformulation. Two sub-goals:
-- (1) `partial_tau_eq_fderiv_apply` — the scalar derivWithin partial in τ equals
--     the (1,0)-direction of the joint fderivWithin on the product Icc × Icc.
-- (2) `fderiv_e1_section_has_deriv_in_t` — the fderivWithin (1,0)-section, viewed
--     as a function of t', has the swapped mixed partial as its t-derivative.
-- Transport (2) along the pointwise eq from (1) via `congr_of_eventuallyEq`,
-- using `Icc 0 1 ∈ 𝓝 t` (from `t ∈ Ioo 0 1`) for the neighborhood.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10346

namespace Problems.residue_thm

def partial_tau_has_deriv_in_t := @Problems.residue_thm.s10346

end Problems.residue_thm
