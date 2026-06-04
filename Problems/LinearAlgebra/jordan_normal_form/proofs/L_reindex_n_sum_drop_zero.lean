-- Decompose into three abstract sub-goals:
-- (i) `inl_zero_n_eq` — N(v⟨inl t, 0⟩) = 0 via hd's j=0 branch + hv_chain;
-- (ii) `inr_zero_n_eq` — N(v⟨inr c, 0⟩) = 0 since cb c ∈ C ⊆ ker N;
-- (iii) `sigma_drop_zero` — sigma-sum bookkeeping: any f vanishing on
--   inl-0 / inr indices equals its inl-succ sub-sum.
-- Closer applies (iii) to f := g • N ∘ v, discharging its premises via
-- (i)/(ii) wrapped by `smul_zero`.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11055

namespace Problems.LinearAlgebra.jordan_normal_form

def reindex_n_sum_drop_zero := @Problems.LinearAlgebra.jordan_normal_form.s11055

end Problems.LinearAlgebra.jordan_normal_form
