import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- inl_succ_collapse: sigma-sum over inl-succ indices equals full sum when inl/inr bottoms vanish.
-- Splits LHS via Fintype.sum_sigma + Fintype.sum_sum_type; inr part dies by Fin.sum_univ_one + h2;
-- inl inner sum peeled by Fin.sum_univ_succ + h1, leaving exactly the succ-indexed sigma sum.
-- entry_kind: Builder
theorem inl_succ_collapse
    {M : Type*} [AddCommMonoid M]
    (p : ℕ) (l : Fin p → ℕ) (m : ℕ)
    (f : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → M)
    (h1 : ∀ t : {t : Fin p // 0 < l t}, f ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0)
    (h2 : ∀ c : Fin m, f ⟨Sum.inr c, (0 : Fin 1)⟩ = 0) :
    (∑ i, f i) = ∑ ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1),
      f ⟨Sum.inl ti.1, ti.2.succ⟩ := by
  simp_rw [Fintype.sum_sigma]
  rw [Fintype.sum_sum_type]
  have hinr : ∑ c : Fin m, ∑ j : Fin (Sum.elim
      (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) (Sum.inr c)),
      f ⟨Sum.inr c, j⟩ = 0 := by
    apply Finset.sum_eq_zero; intro c _
    rw [show (∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
                (fun _ : Fin m => 1) (Sum.inr c)), f ⟨Sum.inr c, j⟩)
            = ∑ j : Fin 1, f ⟨Sum.inr c, j⟩ from rfl,
        Fin.sum_univ_one]
    exact h2 c
  rw [hinr, add_zero]
  apply Finset.sum_congr rfl; intro t _
  rw [show (∑ j : Fin (Sum.elim (fun t' : {t : Fin p // 0 < l t} => l t'.1 + 1)
              (fun _ : Fin m => 1) (Sum.inl t)), f ⟨Sum.inl t, j⟩)
          = ∑ j : Fin (l t.1 + 1), f ⟨Sum.inl t, j⟩ from rfl,
      Fin.sum_univ_succ, h1 t, zero_add]

end Problems.LinearAlgebra.jordan_normal_form
