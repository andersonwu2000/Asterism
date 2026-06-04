-- Decompose into one strictly-more-abstract sub-goal: the pure sum-bookkeeping
-- identity, generic in `D`/`CB` (no `N`, no `LinearMap.range`, no `hd`).
-- Instantiate with `D := ↑(d ·)`, `CB := ↑(cb ·)` to recover the parent shape.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11056

namespace Problems.LinearAlgebra.jordan_normal_form

def comp_block_eq_neg_chain_bottoms_2 := @Problems.LinearAlgebra.jordan_normal_form.s11056

end Problems.LinearAlgebra.jordan_normal_form
