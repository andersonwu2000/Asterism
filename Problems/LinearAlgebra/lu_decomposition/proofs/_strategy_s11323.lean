import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs.L_lu_step_assembly
import Problems.LinearAlgebra.lu_decomposition.proofs.L_schur_complement_minors

namespace Problems.LinearAlgebra.lu_decomposition

-- Inductive step decomposed via Schur complement:
--   1. `schur_complement_minors` — principal minors of the Schur complement
--      `S i j = A i.succ j.succ - A i.succ 0 * A 0 j.succ / A 0 0` are nonzero,
--      inherited from A's.
--   2. `lu_step_assembly` — given LU of the Schur complement, assemble LU of A
--      via the standard block-triangular construction.
-- Combine: extract `a₁₁ ≠ 0` from the `k = 1` minor hypothesis, build `S`,
-- apply IH via `schur_complement_minors`, then `lu_step_assembly` closes.
theorem s11323 : ∀ {n : ℕ},
    (∀ {𝕜 : Type} [Field 𝕜] (A : Matrix (Fin n) (Fin n) 𝕜),
      (∀ k (hk : k ≤ n),
        (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) →
      ∃ L U : Matrix (Fin n) (Fin n) 𝕜,
        (L.BlockTriangular fun i : Fin n => (n - 1 : ℕ) - (i : ℕ)) ∧
        (U.BlockTriangular fun i : Fin n => (i : ℕ)) ∧
        (∀ i, L i i = 1) ∧
        A = L * U) →
    ∀ {𝕜 : Type} [Field 𝕜] (A : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜),
    (∀ k (hk : k ≤ n + 1),
      (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) →
    ∃ L U : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜,
      (L.BlockTriangular fun i : Fin (n + 1) => (n + 1 - 1 : ℕ) - (i : ℕ)) ∧
      (U.BlockTriangular fun i : Fin (n + 1) => (i : ℕ)) ∧
      (∀ i, L i i = 1) ∧
      A = L * U  := by
  intro n ih 𝕜 _ A hPM
  have ha : A 0 0 ≠ 0 := by
    have h1 := hPM 1 (Nat.succ_le_succ (Nat.zero_le _))
    have heq : (A.submatrix (Fin.castLE (Nat.succ_le_succ (Nat.zero_le n)))
        (Fin.castLE (Nat.succ_le_succ (Nat.zero_le n)))).det = A 0 0 := by
      simp [Matrix.submatrix_apply, Fin.castLE]
    rw [heq] at h1
    exact h1
  set S : Matrix (Fin n) (Fin n) 𝕜 :=
    fun i j => A i.succ j.succ - A i.succ 0 * A 0 j.succ / A 0 0 with hS_def
  have hS_minors : ∀ k (hk : k ≤ n),
      (S.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0 :=
    schur_complement_minors A hPM
  obtain ⟨L', U', hL', hU', hL'_diag, hS_eq⟩ := ih S hS_minors
  exact lu_step_assembly A ha L' U' hL' hU' hL'_diag hS_eq.symm

end Problems.LinearAlgebra.lu_decomposition
