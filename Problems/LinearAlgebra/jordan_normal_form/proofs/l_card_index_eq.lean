import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- card_index_eq: Fintype.card_sigma + Sum.elim unfolding + subtype-sum vs full-sum via
-- Fintype.sum_subtype_add_sum_subtype; purely combinatorial, no linear algebra.
-- entry_kind: Builder
theorem card_index_eq (p : ℕ) (l : Fin p → ℕ) (m : ℕ) :
    Fintype.card (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s))
        = (∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m := by
  have h1 : ∑ s : {t : Fin p // 0 < l t}, l ↑s = ∑ t : Fin p, l t := by
    conv_rhs =>
      rw [← Fintype.sum_subtype_add_sum_subtype (fun t : Fin p => 0 < l t) (fun t => l t)]
    have h_neg : ∑ x : {t : Fin p // ¬0 < l t}, l ↑x = 0 :=
      Finset.sum_eq_zero (fun x _ => Nat.eq_zero_of_not_pos x.prop)
    linarith
  have hcard : ∑ _s : {t : Fin p // 0 < l t}, (1:ℕ) = Fintype.card {t : Fin p // 0 < l t} := by
    rw [Finset.sum_const, Finset.card_univ]; simp
  have hm : ∑ _s : Fin m, (1:ℕ) = m := by simp
  simp only [Fintype.card_sigma, Fintype.card_fin, Fintype.sum_sum_type,
    Sum.elim_inl, Sum.elim_inr, Finset.sum_add_distrib]
  linarith

end Problems.LinearAlgebra.jordan_normal_form
