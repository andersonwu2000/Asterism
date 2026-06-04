-- Mirror the abstract 3-step decomposition pattern: linearity → reindex/drop-zero → per-element shift.
-- (1) `n_distrib_smul_sum`: N distributes through `∑ g i • v i` into `∑ g i • N (v i)`.
-- (2) `n_sum_collapse_to_inl_succ`: drop vanishing inl-bottom and inr-bottom terms; reindex
--     surviving inl-succ terms to `Σ t, Fin (l t.1)`.
-- (3) `n_v_inl_succ_eq_d`: per-element chain shift `N (v ⟨inl t, j.succ⟩) = d ⟨t.1, j⟩`.
-- Combiner: rewrite by (1) and (2), then `Finset.sum_congr` applies (3) pointwise inside `g • _`.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11057

namespace Problems.LinearAlgebra.jordan_normal_form

def pushforward_d_eq_alias := @Problems.LinearAlgebra.jordan_normal_form.s11057

end Problems.LinearAlgebra.jordan_normal_form
