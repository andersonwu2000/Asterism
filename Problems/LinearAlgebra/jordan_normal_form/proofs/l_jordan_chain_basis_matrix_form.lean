import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- jordan_chain_basis_matrix_form: chain-basis structure for nilpotent N implies IsJordanForm
-- and zero diagonal, by reading column structure via LinearMap.toMatrix_apply.
theorem jordan_chain_basis_matrix_form
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (b : Module.Basis (Fin (Module.finrank K W)) K W)
    (hb : ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i) :
    IsJordanForm (LinearMap.toMatrix b b N) ∧
      ∀ i : Fin (Module.finrank K W), (LinearMap.toMatrix b b N) i i = 0 := by
  have mij : ∀ (i j : Fin (Module.finrank K W)),
      (LinearMap.toMatrix b b N) i j = b.repr (N (b j)) i :=
    fun i j => LinearMap.toMatrix_apply b b N i j
  -- when N(b j) = b k, entry (i,j) = if k = i then 1 else 0
  have col_basis : ∀ (i j k : Fin (Module.finrank K W)),
      N (b j) = b k → (LinearMap.toMatrix b b N) i j = if k = i then 1 else 0 := by
    intro i j k h; rw [mij, h, Module.Basis.repr_self_apply]
  -- diagonal is zero: N(b i) = 0 or N(b i) = b k with (k:ℕ)+1 = (i:ℕ), so k ≠ i
  have diag_zero : ∀ i : Fin (Module.finrank K W),
      (LinearMap.toMatrix b b N) i i = 0 := by
    intro i
    rcases hb i with h | ⟨k, hki, hNi⟩
    · simp [mij, h]
    · rw [col_basis i i k hNi, if_neg]
      exact fun heq => absurd hki (by rw [congrArg Fin.val heq]; omega)
  refine ⟨fun i j => ?_, diag_zero⟩
  show (if (i : ℕ) = (j : ℕ) then True
        else if (i : ℕ) + 1 = (j : ℕ) then
          (LinearMap.toMatrix b b N) i j = 0 ∨
            ((LinearMap.toMatrix b b N) i j = 1 ∧
              (LinearMap.toMatrix b b N) i i = (LinearMap.toMatrix b b N) j j)
        else (LinearMap.toMatrix b b N) i j = 0)
  rcases hb j with h | ⟨k, hkj, hNj⟩
  · -- N(b j) = 0: entry (i,j) = 0 in all positions
    have hij0 : (LinearMap.toMatrix b b N) i j = 0 := by simp [mij, h]
    split_ifs <;> simp [hij0]
  · -- N(b j) = b k: entry (i,j) = if k = i then 1 else 0
    rw [col_basis i j k hNj]
    by_cases hki : k = i
    · -- k = i: entry is 1; hkj says k+1=j, so after subst i replaced by k
      subst hki
      simp only [if_true]
      -- goal: if ↑k=↑j then True else if ↑k+1=↑j then 1=0∨True∧Mkk=Mjj else 1=0
      rw [if_neg (show ¬ (k : ℕ) = (j : ℕ) from by omega), if_pos hkj]
      -- goal: 1 = 0 ∨ True ∧ M k k = M j j
      exact Or.inr ⟨trivial, by simp [diag_zero]⟩
    · -- k ≠ i: entry is 0
      simp only [if_neg hki]
      split_ifs <;> simp

end Problems.LinearAlgebra.jordan_normal_form
