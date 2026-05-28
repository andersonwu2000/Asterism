import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs

namespace Problems.LinearAlgebra.lu_decomposition

-- lu_step_assembly: assemble LU from Schur IH via Fin.cases block construction
-- L: 1/0/scaled-col/L'; U: pivot/row/0/U'; hSchur closes bottom-right block
theorem lu_step_assembly {n : ℕ} {𝕜 : Type} [Field 𝕜]
    (A : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜)
    (ha : A 0 0 ≠ 0)
    (L' U' : Matrix (Fin n) (Fin n) 𝕜)
    (hL' : L'.BlockTriangular fun i : Fin n => (n - 1 : ℕ) - (i : ℕ))
    (hU' : U'.BlockTriangular fun i : Fin n => (i : ℕ))
    (hL'_diag : ∀ i, L' i i = 1)
    (hSchur : L' * U' =
      (fun (i j : Fin n) =>
        A i.succ j.succ - A i.succ 0 * A 0 j.succ / A 0 0 :
        Matrix (Fin n) (Fin n) 𝕜)) :
    ∃ L U : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜,
      (L.BlockTriangular fun i : Fin (n + 1) => (n + 1 - 1 : ℕ) - (i : ℕ)) ∧
      (U.BlockTriangular fun i : Fin (n + 1) => (i : ℕ)) ∧
      (∀ i, L i i = 1) ∧
      A = L * U := by
  let L : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜 := Matrix.of fun i j =>
    Fin.cases (motive := fun _ => Fin (n + 1) → 𝕜)
      (fun i => Fin.cases 1 (fun _ => 0) i)
      (fun i' i => Fin.cases (A i'.succ 0 / A 0 0) (fun j' => L' i' j') i) i j
  let U : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜 := Matrix.of fun i j =>
    Fin.cases (motive := fun _ => Fin (n + 1) → 𝕜)
      (fun i => Fin.cases (A 0 0) (fun j' => A 0 j'.succ) i)
      (fun i' i => Fin.cases 0 (fun j' => U' i' j') i) i j
  refine ⟨L, U, ?_, ?_, ?_, ?_⟩
  · -- L is BlockTriangular (lower triangular)
    intro i j hij
    simp only [L, Matrix.of_apply]
    revert j
    refine Fin.cases ?_ ?_ i
    · refine Fin.cases ?_ ?_
      · intro h; simp only [Fin.val_zero] at h; omega
      · intro j _; simp [Fin.cases_zero, Fin.cases_succ]
    · intro i'
      refine Fin.cases ?_ ?_
      · intro h; simp only [Fin.val_zero, Fin.val_succ] at h; omega
      · intro j' hij
        apply hL'
        simp only [Fin.val_succ, Nat.sub_right_comm] at hij ⊢
        exact hij
  · -- U is BlockTriangular (upper triangular)
    intro i j hij
    simp only [U, Matrix.of_apply]
    revert j
    refine Fin.cases ?_ ?_ i
    · refine Fin.cases ?_ ?_
      · intro h; simp only [Fin.val_zero] at h; omega
      · intro j h; simp only [Fin.val_zero, Fin.val_succ] at h; omega
    · intro i'
      refine Fin.cases ?_ ?_
      · intro _; simp [Fin.cases_succ, Fin.cases_zero]
      · intro j' hij
        apply hU'
        dsimp only
        simp only [Fin.val_succ] at hij; omega
  · -- Diagonal of L equals 1
    intro i
    refine Fin.cases ?_ ?_ i
    · simp [L, Matrix.of_apply, Fin.cases_zero]
    · intro i'; simp [L, Matrix.of_apply, Fin.cases_succ, hL'_diag]
  · -- A = L * U entrywise
    ext i j
    simp only [Matrix.mul_apply, L, U, Matrix.of_apply]
    revert j
    refine Fin.cases ?_ ?_ i
    · refine Fin.cases ?_ ?_
      · simp [Fin.sum_univ_succ, Fin.cases_zero, Fin.cases_succ]
      · intro j'; simp [Fin.sum_univ_succ, Fin.cases_zero, Fin.cases_succ]
    · intro i'
      refine Fin.cases ?_ ?_
      · simp only [Fin.sum_univ_succ, Fin.cases_succ, Fin.cases_zero,
                   mul_zero, Finset.sum_const_zero, add_zero]
        field_simp
      · intro j'
        simp only [Fin.sum_univ_succ, Fin.cases_succ, Fin.cases_zero]
        have hS := congr_fun (congr_fun hSchur i') j'
        simp only [Matrix.mul_apply] at hS
        rw [hS]; ring

end Problems.LinearAlgebra.lu_decomposition
