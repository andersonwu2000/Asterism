-- Pointwise on `Ioo (1/2) 1`, rewrite the integrand via two sub-goals:
-- `right_half_path_value_eq_on_ioo` (γ t = β' (2t-1)) and
-- `right_half_deriv_value_eq_on_ioo` (deriv γ t = 2 * derivWithin β' (Icc 0 1) (2t-1)),
-- then close by congruence (rw the two equalities under `Q _ * _`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10679

namespace Problems.residue_thm

def right_half_integrand_eq_on_ioo := @Problems.residue_thm.s10679

end Problems.residue_thm
