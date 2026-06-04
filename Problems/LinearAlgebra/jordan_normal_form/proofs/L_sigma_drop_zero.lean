import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- sigma_drop_zero: drop zero-indexed (inl-0 and inr) terms from sigma sum using h_inl/h_inr
-- Splits the sigma sum over (A⊕B, fiber) into inl/inr parts, zeroes out inr (Fin 1 fibers)
-- and the j=0 term of each inl fiber, leaving only the inl-succ sub-sum.
theorem sigma_drop_zero
    {W : Type*} [AddCommGroup W]
    (p : ℕ) (l : Fin p → ℕ) (m : ℕ)
    (f : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
            (fun _ : Fin m => 1) s)) → W)
    (h_inl : ∀ t : {t : Fin p // 0 < l t}, f ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0)
    (h_inr : ∀ c : Fin m, f ⟨Sum.inr c, (0 : Fin 1)⟩ = 0) :
    (∑ i, f i) = ∑ ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1),
      f ⟨Sum.inl ti.1, ti.2.succ⟩ := by
  rw [Fintype.sum_sigma, Fintype.sum_sum_type]
  conv_rhs => rw [Fintype.sum_sigma]
  simp only [Sum.elim_inl]
  have hinr : ∑ x : Fin m, ∑ y : Fin (Sum.elim
      (fun (t : {t : Fin p // 0 < l t}) => l t.1 + 1) (fun _ : Fin m => 1)
      (Sum.inr x)), f ⟨Sum.inr x, y⟩ = 0 := by
    apply Finset.sum_eq_zero; intro x _
    change ∑ _y : Fin 1, _ = 0
    simp [h_inr]
  rw [hinr, add_zero]
  congr 1; ext x
  change (∑ y : Fin (l ↑x + 1), f ⟨Sum.inl x, y⟩) = ∑ j : Fin (l ↑x), f ⟨Sum.inl x, j.succ⟩
  rw [Fin.sum_univ_succ, h_inl, zero_add]

end Problems.LinearAlgebra.jordan_normal_form