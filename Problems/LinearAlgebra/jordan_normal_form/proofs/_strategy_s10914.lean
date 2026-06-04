import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Entrywise check that the reindexed block-diagonal matrix is Jordan.
-- Off-block entries vanish (`blockDiagonal'_apply_ne`); on-block entries equal the block's
-- entries (`blockDiagonal'_apply_eq`), and `he` transfers the `+1`-adjacency so each block's
-- `IsJordanForm` (`hjor`) closes the per-entry condition.
theorem s10914
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))]
    (b : Module.Basis ((μ : K) × Fin (n μ)) K V)
    (Mμ : (μ : K) → Matrix (Fin (n μ)) (Fin (n μ)) K)
    (hb : LinearMap.toMatrix b b T = Matrix.blockDiagonal' Mμ)
    (hjor : ∀ μ : K, IsJordanForm (Mμ μ))
    (e : Fin (Module.finrank K V) ≃ ((μ : K) × Fin (n μ)))
    (he : ∀ p q : Fin (Module.finrank K V), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))) :
    IsJordanForm ((Matrix.blockDiagonal' Mμ).submatrix e e)  := by
  intro i j
  by_cases hij : (i : ℕ) = (j : ℕ)
  · rw [if_pos hij]; trivial
  · rw [if_neg hij]
    have hadj := he i j
    have hijne : i ≠ j := fun h => hij (congrArg Fin.val h)
    have hene : e i ≠ e j := fun h => hijne (e.injective h)
    simp only [Matrix.submatrix_apply]
    rcases hei : e i with ⟨μi, ki⟩
    rcases hej : e j with ⟨μj, kj⟩
    rw [hei, hej] at hadj hene
    by_cases hμ : μi = μj
    · subst hμ
      rw [Matrix.blockDiagonal'_apply_eq, Matrix.blockDiagonal'_apply_eq,
        Matrix.blockDiagonal'_apply_eq]
      have hkne : ki ≠ kj := fun h => hene (by rw [h])
      have hkv : (ki : ℕ) ≠ (kj : ℕ) := fun h => hkne (Fin.val_injective h)
      have hb := hjor μi ki kj
      rw [if_neg hkv] at hb
      have hiff := hadj rfl
      split_ifs with hij1
      · rw [if_pos (hiff.mpr hij1)] at hb; exact hb
      · rw [if_neg (fun h => hij1 (hiff.mp h))] at hb; exact hb
    · rw [Matrix.blockDiagonal'_apply_ne Mμ ki kj hμ]
      split_ifs <;> simp


end Problems.LinearAlgebra.jordan_normal_form
