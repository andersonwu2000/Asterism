import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs

namespace Problems.LinearAlgebra.lu_decomposition

open Matrix

-- Direct proof via `Matrix.fromBlocks` decomposition and `det_fromBlocks₁₁`.
-- Build the equivalence `Fin (m+1) ≃ Fin 1 ⊕ Fin m` (0 ↦ inl 0, succ ↦ inr),
-- express M as the reindexed block matrix, then use the Schur-complement
-- determinant identity; the (D - C * ⅟A * B) block matches the goal's
-- Matrix.of expression after collapsing the 1×1 inverse.
theorem s11329 {m : ℕ} {𝕜 : Type} [Field 𝕜]
    (M : Matrix (Fin (m + 1)) (Fin (m + 1)) 𝕜) (h00 : M 0 0 ≠ 0) :
    M.det = M 0 0 * (Matrix.of fun (i j : Fin m) =>
      M i.succ j.succ - M i.succ 0 * M 0 j.succ / M 0 0).det  := by
  let e : Fin (m + 1) ≃ Fin 1 ⊕ Fin m :=
  { toFun := fun i => Fin.cases (Sum.inl 0) Sum.inr i
    invFun := fun s => Sum.elim (fun _ => (0 : Fin (m + 1))) Fin.succ s
    left_inv := fun i => by
      refine Fin.cases ?_ ?_ i
      · simp
      · intro j; simp
    right_inv := fun s => by
      rcases s with ⟨k, hk⟩ | j
      · interval_cases k; simp
      · simp }
  let A : Matrix (Fin 1) (Fin 1) 𝕜 := fun _ _ => M 0 0
  let B : Matrix (Fin 1) (Fin m) 𝕜 := fun _ j => M 0 j.succ
  let C : Matrix (Fin m) (Fin 1) 𝕜 := fun i _ => M i.succ 0
  let D : Matrix (Fin m) (Fin m) 𝕜 := fun i j => M i.succ j.succ
  have hM : M = (Matrix.fromBlocks A B C D).submatrix e e := by
    ext i j
    refine Fin.cases ?_ ?_ i
    · refine Fin.cases ?_ ?_ j
      · simp [A, e, Matrix.submatrix_apply, Matrix.fromBlocks_apply₁₁]
      · intro j'
        simp [B, e, Matrix.submatrix_apply, Matrix.fromBlocks_apply₁₂]
    · intro i'
      refine Fin.cases ?_ ?_ j
      · simp [C, e, Matrix.submatrix_apply, Matrix.fromBlocks_apply₂₁]
      · intro j'
        simp [D, e, Matrix.submatrix_apply, Matrix.fromBlocks_apply₂₂]
  haveI : Invertible (A.det) := by
    rw [show A.det = M 0 0 by simp [A]]
    exact invertibleOfNonzero h00
  haveI : Invertible A := Matrix.invertibleOfDetInvertible A
  have hdet : M.det = A.det * (D - C * ⅟A * B).det := by
    conv_lhs => rw [hM]
    rw [Matrix.det_submatrix_equiv_self, Matrix.det_fromBlocks₁₁]
  rw [hdet]
  have hA : A.det = M 0 0 := by simp [A]
  rw [hA]
  congr 1
  congr 1
  ext i j
  simp only [Matrix.sub_apply, Matrix.mul_apply, Matrix.of_apply, Fin.sum_univ_one]
  change M i.succ j.succ - C i 0 * (⅟ A) 0 0 * B 0 j = _
  have hinvA : (⅟ A) 0 0 = (M 0 0)⁻¹ := by
    rw [Matrix.invOf_eq_nonsing_inv, Matrix.inv_def]
    simp [A, Matrix.adjugate_fin_one]
  rw [hinvA]
  change M i.succ j.succ - M i.succ 0 * (M 0 0)⁻¹ * M 0 j.succ = _
  field_simp

end Problems.LinearAlgebra.lu_decomposition
