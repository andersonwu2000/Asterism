-- Two τ'-functions agree pointwise on `Icc 0 1`:
--   F τ' = fderivWithin H U (τ', t) (0,1)   and   G τ' = deriv (H τ') t.
-- The pointwise identity uses lesson-34 in the t-direction (uses `t ∈ Ioo 0 1`
-- so `Icc 0 1 ∈ 𝓝 t`, unlocking `fderivWithin (·,t)→(0,1) = deriv (H τ') t`).
-- Apply `derivWithin_congr` to lift pointwise equality to derivWithin equality at τ.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10393

namespace Problems.residue_thm

def deriv_within_section_fderiv_eq_deriv := @Problems.residue_thm.s10393

end Problems.residue_thm
