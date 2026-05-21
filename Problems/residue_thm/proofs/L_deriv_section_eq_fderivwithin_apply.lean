-- Two-step transfer: (1) `deriv (H τ') t = derivWithin (H τ') (Icc 0 1) t` via
-- `derivWithin_of_mem_nhds` since `Icc 0 1 ∈ 𝓝 t` for interior `t ∈ Ioo 0 1`;
-- (2) the slice chain rule sub-goal `derivwithin_eq_fderivwithin_section_t`
-- handles `derivWithin (H τ') (Icc 0 1) t = fderivWithin G (Icc×Icc) (τ',t) (0,1)`
-- using `HasFDerivWithinAt.comp_hasDerivWithinAt_of_eq` on the slice `t' ↦ (τ',t')`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10360

namespace Problems.residue_thm

def deriv_section_eq_fderivwithin_apply := @Problems.residue_thm.s10360

end Problems.residue_thm
