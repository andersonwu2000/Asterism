-- Equate `deriv (H p.1) p.2` on `Ioo×Ioo` to evaluation of the joint
-- Fréchet derivative `fderiv (H ·.1 ·.2) p (0,1)`, then transport
-- ContDiffOn ℝ 1 of the fderiv-evaluation form across the equality.
-- (a) `eq_partial_t_to_fderiv_apply` is a pointwise differential-calculus
-- identity (Builder).  (b) `contdiffon_fderiv_apply_partial_t` follows from
-- `ContDiffOn.fderiv_of_isOpen` (drops one order on an open set) composed
-- with the continuous-linear evaluation map at `(0,1)` (Backward).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10348

namespace Problems.residue_thm

def partial_t_h_contdiffon_ioo := @Problems.residue_thm.s10348

end Problems.residue_thm
