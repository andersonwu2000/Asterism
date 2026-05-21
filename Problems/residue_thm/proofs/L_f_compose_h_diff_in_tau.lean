-- Direct chain-rule proof: extract a C¹ section `fun τ' => H τ' t` from the
-- joint `ContDiffOn ℝ 2 H` at interior `(x, t) ∈ Ioo × Ioo`, get its ℝ-
-- differentiability at `x`, get ℂ-differentiability of `f` at `H x t ∈ V`
-- from analyticity, then chain via `HasDerivAt.comp`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10342

namespace Problems.residue_thm

def f_compose_h_diff_in_tau := @Problems.residue_thm.s10342

end Problems.residue_thm
