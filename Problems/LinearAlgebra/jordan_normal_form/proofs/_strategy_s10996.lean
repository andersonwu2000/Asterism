import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct combinatorial count (leaf): card_sigma + card_fin reduce the LHS to a sum over the
-- sum-index, sum_sum_type splits it into the two summands `∑ (l t.1 + 1)` and `∑ 1 = m`.
-- sum_add_distrib peels the chain-length sum from the per-block `+1`; the `+1`s count the
-- nonzero-l blocks (= card subtype), and `sum_subtype`+`sum_subset` extend the subtype sum
-- of `l` to all of `Fin p` (the dropped `l t = 0` terms vanish), matching the RHS normal form.
theorem s10996 (p : ℕ) (l : Fin p → ℕ) (m : ℕ) :
    Fintype.card (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s))
        = (∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m  := by
  rw [Fintype.card_sigma]
  simp only [Fintype.card_fin]
  rw [Fintype.sum_sum_type]
  simp only [Sum.elim_inl, Sum.elim_inr, Finset.sum_const, smul_eq_mul, mul_one,
    Finset.card_univ, Fintype.card_fin]
  rw [Finset.sum_add_distrib]
  have h2 : (∑ _x : {t : Fin p // 0 < l t}, (1:ℕ)) = Fintype.card {t : Fin p // 0 < l t} := by
    simp [Finset.card_univ]
  have h1 : (∑ x : {t : Fin p // 0 < l t}, l ↑x) = ∑ t, l t := by
    rw [← Finset.sum_subtype (Finset.univ.filter (fun t => 0 < l t)) (fun x => by simp) l]
    apply Finset.sum_subset (Finset.filter_subset _ _)
    intro x _ hx
    simp only [Finset.mem_filter, Finset.mem_univ, true_and, not_lt, Nat.le_zero] at hx
    exact hx
  rw [h1, h2]

end Problems.LinearAlgebra.jordan_normal_form
