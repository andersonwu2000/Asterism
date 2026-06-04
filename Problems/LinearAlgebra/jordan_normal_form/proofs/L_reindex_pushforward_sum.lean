-- Collapse `∑ g i • N(v i)` to the inl-succ sub-sum via three sub-lemmas.
-- `inl_bottom_kill`: chain bottom v⟨inl t,0⟩ ↦ 0 (re-declares the proved sibling).
-- `inr_bottom_kill`: complement bottom v⟨inr c,0⟩ ↦ 0 (re-declares the proved sibling).
-- `inl_succ_collapse`: generic sigma identity — given f vanishes at inl/inr bottoms,
--   ∑ f reduces to the inl-succ-indexed sub-sum (re-declares the proved sibling).
-- Combine via `refine inl_succ_collapse p l m (fun i => g i • N(v i)) ?_ ?_`; the
-- two side conditions discharge by `simp only [h_*_zero, smul_zero]`, which
-- beta-reduces the lambda before the rewrites — fixing the s11020 combiner failure
-- (`rw [h_inl_zero t]` failed to match inside an un-beta'd `(fun i => …) ⟨…, 0⟩`).
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11035

namespace Problems.LinearAlgebra.jordan_normal_form

def reindex_pushforward_sum := @Problems.LinearAlgebra.jordan_normal_form.s11035

end Problems.LinearAlgebra.jordan_normal_form
