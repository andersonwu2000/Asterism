-- Specialize Mathlib's `intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le`
-- to the segment integrand. Three Builder sub-goals supply the FTC ingredients
-- for the composite `F ∘ (t ↦ z + t·(w-z))` on `Icc 0 1`:
-- (1) `seg_f_comp_continuous` — continuity on the closed interval,
-- (2) `seg_f_comp_hasderivat_ioo` — chain rule on the open interior
--     (uses `Icc 0 1 ∈ 𝓝 t` for `t ∈ Ioo 0 1`, sidestepping the boundary trap),
-- (3) `seg_integrand_integrable` — IntervalIntegrable of the integrand.
-- Combinator: feed to `integral_eq_sub_of_hasDerivAt_of_le` and collapse
-- endpoints `z + 0·(w-z) ↦ z`, `z + 1·(w-z) ↦ w` via `push_cast; ring`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10632

namespace Problems.residue_thm

def segment_integral_eq_primitive_diff_in_ball := @Problems.residue_thm.s10632

end Problems.residue_thm
