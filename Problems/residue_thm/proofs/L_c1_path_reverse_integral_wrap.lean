-- Take β_rev := β ∘ (1 - ·). Decompose into three sub-pieces matching the proved-sibling
-- shape of s10539: (1) ContDiffOn ℝ 1 of β∘(1-·), (2) pointwise avoidance, (3) integral
-- sign-flip via chain rule + substitution. Endpoint equalities collapse by `norm_num`.
-- Each sub-goal restates one strictly-smaller component (no hβ_avoid in c1, no Q in c1/avoid),
-- and the framework's proved-sibling auto-import is reached from each Builder wrapper.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10658

namespace Problems.residue_thm

def c1_path_reverse_integral_wrap := @Problems.residue_thm.s10658

end Problems.residue_thm
