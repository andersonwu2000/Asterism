-- The complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`, via two sub-goals.
--   * `comp_block_eq_neg_chain_bottoms` : pure sum bookkeeping using `hg`, `habove`,
--     `hv_chain`, `hv_C` to rewrite the block as `-(∑ t, g⟨inl t,0⟩ • d⟨t.1,0⟩)`.
--     Strictly simpler: no `range N` reasoning, no linear independence.
--   * `chain_bottoms_mem_range` : the chain-bottom sum lies in `range N` since each
--     `↑(d ·) ∈ range N` and `range N` is closed under scalar mul + finite sum.
--     Strictly simpler: pure submodule closure facts, no full sum identity.
-- Combinator: rewrite via the equality, then `neg_mem` on the membership.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11034

namespace Problems.LinearAlgebra.jordan_normal_form

def comp_combo_mem_range := @Problems.LinearAlgebra.jordan_normal_form.s11034

end Problems.LinearAlgebra.jordan_normal_form
