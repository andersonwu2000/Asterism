-- Take β_rev := β ∘ (1 - ·). The endpoint equalities reduce by `simp` after `1 - 0 = 1`,
-- `1 - 1 = 0`. The three non-trivial sub-goals are: C¹ via composition with the smooth map
-- (1 - ·), pointwise avoidance via `1 - t ∈ Icc 0 1`, and the integral sign-flip via the
-- chain rule (`deriv (fun s => β (1 - s)) t = -deriv β (1 - t)`) plus substitution `u = 1 - t`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10539

namespace Problems.residue_thm

def c1_path_reverse_integral := @Problems.residue_thm.s10539

end Problems.residue_thm
