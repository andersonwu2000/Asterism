-- Bridge `fderivWithin ... (τ',t) (0,1)` to `deriv (H τ') t` through the section
-- `derivWithin (H τ') (Icc 0 1) t`. Sub-goal A (lesson-34) ties `derivWithin` to
-- the joint `fderivWithin` in the t-direction; sub-goal B uses `t ∈ Ioo 0 1` so
-- `Icc 0 1 ∈ 𝓝 t` and `derivWithin = deriv` there.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10399

namespace Problems.residue_thm

def fderiv_within_dir_t_eq_deriv_t_section := @Problems.residue_thm.s10399

end Problems.residue_thm
