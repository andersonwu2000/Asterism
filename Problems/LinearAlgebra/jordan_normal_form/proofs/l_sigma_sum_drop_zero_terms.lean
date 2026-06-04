import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- sigma_sum_drop_zero_terms: collapse sum over Σ(A⊕B),Fin(Sum.elim fA fB) to inl-succ sub-sum
-- by splitting inl/inr via Fintype.sum_sum_type, dropping zero terms via h1/h2/Fin.sum_univ_succ
theorem sigma_sum_drop_zero_terms
    {M : Type*} [AddCommMonoid M]
    (p : ℕ) (l : Fin p → ℕ) (m : ℕ)
    (f : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → M)
    (h1 : ∀ t : {t : Fin p // 0 < l t}, f ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0)
    (h2 : ∀ c : Fin m, f ⟨Sum.inr c, (0 : Fin 1)⟩ = 0) :
    (∑ i, f i) = ∑ ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1),
      f ⟨Sum.inl ti.1, ti.2.succ⟩ := by
  -- Step 1: expand both sides via sum_sigma
  conv_lhs =>
    rw [show (Finset.univ : Finset (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
        Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s))) =
      Finset.sigma Finset.univ (fun _ => Finset.univ) from Finset.univ_sigma_univ.symm]
    rw [Finset.sum_sigma]
  conv_rhs =>
    rw [show (Finset.univ : Finset (Σ t : {t : Fin p // 0 < l t}, Fin (l t.1))) =
      Finset.sigma Finset.univ (fun _ => Finset.univ) from Finset.univ_sigma_univ.symm]
    rw [Finset.sum_sigma]
  -- Step 2: split LHS inl/inr
  rw [Fintype.sum_sum_type]
  -- Step 3: inr sum = 0
  have rhs_zero : ∑ x : Fin m,
      ∑ s : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
        (fun _ : Fin m => 1) (Sum.inr x)), f ⟨Sum.inr x, s⟩ = 0 := by
    apply Finset.sum_eq_zero; intro x _
    change (∑ _ : Fin 1, _) = 0
    rw [Fin.sum_univ_one]; exact h2 x
  -- Step 4: inl inner sum: drop j=0 via Fin.sum_univ_succ + h1
  have lhs_succ : ∀ x : {t : Fin p // 0 < l t},
      ∑ s : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
        (fun _ : Fin m => 1) (Sum.inl x)), f ⟨Sum.inl x, s⟩ =
      ∑ s : Fin (l x.1), f ⟨Sum.inl x, s.succ⟩ := by
    intro x
    change (∑ s : Fin (l x.1 + 1), f ⟨Sum.inl x, s⟩) = ∑ s : Fin (l x.1), f ⟨Sum.inl x, s.succ⟩
    rw [Fin.sum_univ_succ, h1, zero_add]
  rw [Finset.sum_congr rfl (fun x _ => lhs_succ x), rhs_zero, add_zero]



end Problems.LinearAlgebra.jordan_normal_form
