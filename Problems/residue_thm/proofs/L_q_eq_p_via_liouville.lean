-- Liouville bootstrap on the explicit gluing `h_ext z := if z = a then g a else Q z - P z`.
-- Sub-goal `glued_qmp_differentiable_entire` proves h_ext is entire; sub-goal
-- `glued_qmp_tendsto_cocompact_zero` proves it vanishes at ∞.
-- Liouville's `Differentiable.apply_eq_of_tendsto_cocompact` then forces h_ext ≡ 0,
-- and off `a` we have h_ext z = Q z - P z, giving Q z = P z.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10544

namespace Problems.residue_thm

def q_eq_p_via_liouville := @Problems.residue_thm.s10544

end Problems.residue_thm
