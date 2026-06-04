-- Decompose `N (∑ gᵢ • vᵢ) = ∑_{t,j} g⟨inl t, j.succ⟩ • d⟨t.1, j⟩` into three abstract steps:
-- (1) push N through the smul sum (`push_n_smul_sum`); (2) drop the vanishing inl-zero
-- and inr-zero terms and reindex the survivors to `Σ t, Fin (l t.1)` via `ti.2.succ`
-- (`reindex_n_sum_drop_zero`); (3) the per-element chain shift `N (v ⟨inl t, j.succ⟩) = d ⟨t.1, j⟩`
-- (`chain_succ_n_eq_d`). The closer rewrites by (1) and (2), then `Finset.sum_congr` applies (3)
-- pointwise inside the smul. Each sub-goal is strictly more abstract: (1) is pure linearity, (2)
-- is bookkeeping over the sigma index, (3) is the pointwise structural identity.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11029

namespace Problems.LinearAlgebra.jordan_normal_form

def pushforward_d_eq := @Problems.LinearAlgebra.jordan_normal_form.s11029

end Problems.LinearAlgebra.jordan_normal_form
