import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs.L_schur_det_one_succ

namespace Problems.LinearAlgebra.lu_decomposition

-- Reduce the leading-minor Schur factorization to its index-free shape.
-- Set `M` to the (k+1)-leading principal submatrix of `A`; then the goal is the
-- generic identity `det M = M 0 0 * det (Schur M)`. After `rw`-substituting that,
-- `congr 1` closes the residual matrix equality because `Fin.castLE _ i.succ` and
-- `(Fin.castLE _ i).succ` agree by `Fin.val`.
theorem s11326 {n : ℕ} {𝕜 : Type} [Field 𝕜]
    (A : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜)
    (ha : A 0 0 ≠ 0)
    (k : ℕ) (hk : k ≤ n) :
    (A.submatrix (Fin.castLE (Nat.succ_le_succ hk))
                 (Fin.castLE (Nat.succ_le_succ hk))).det =
      A 0 0 * (Matrix.submatrix
        (fun (i j : Fin n) =>
          A i.succ j.succ - A i.succ 0 * A 0 j.succ / A 0 0)
        (Fin.castLE hk) (Fin.castLE hk)).det  := by
  set M := A.submatrix (Fin.castLE (Nat.succ_le_succ hk))
                        (Fin.castLE (Nat.succ_le_succ hk)) with hM_def
  have hM00 : M 0 0 = A 0 0 := by simp [hM_def]
  have hM00_ne : M 0 0 ≠ 0 := by rw [hM00]; exact ha
  have h_schur := schur_det_one_succ M hM00_ne
  rw [h_schur, hM00]
  congr 1

end Problems.LinearAlgebra.lu_decomposition
