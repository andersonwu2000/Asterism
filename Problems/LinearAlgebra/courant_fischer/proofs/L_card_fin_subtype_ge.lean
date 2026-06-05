import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- card_fin_subtype_ge: Fintype.card of {i : Fin n // m ≤ i} equals n - m,
-- proved via explicit bijection with Fin (n - m) sending i ↦ i - m.
theorem card_fin_subtype_ge (n m : ℕ) :
    Fintype.card {i : Fin n // m ≤ (i : ℕ)} = n - m := by
  rw [← Fintype.card_fin (n - m)]
  apply Fintype.card_congr
  refine {
    toFun := fun ⟨⟨i, hi⟩, hm⟩ => ⟨i - m, by omega⟩
    invFun := fun ⟨j, hj⟩ => ⟨⟨m + j, by omega⟩, Nat.le_add_right m j⟩
    left_inv := ?_
    right_inv := ?_
  }
  · intro ⟨⟨i, hi⟩, hm⟩
    simp only [] at hm ⊢
    ext
    simp
    omega
  · intro ⟨j, hj⟩
    ext
    simp
end Problems.LinearAlgebra.courant_fischer
