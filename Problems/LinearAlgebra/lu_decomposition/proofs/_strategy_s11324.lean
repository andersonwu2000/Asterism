import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs.L_a11_ne_zero
import Problems.LinearAlgebra.lu_decomposition.proofs.L_schur_minor_factor

namespace Problems.LinearAlgebra.lu_decomposition

-- Schur complement preserves nonsingularity of leading principal minors:
--   1. `a11_ne_zero` — pivot `A 0 0 ≠ 0` from the `k = 1` minor hypothesis.
--   2. `schur_minor_factor` — for each `k ≤ n`, the `(k+1)×(k+1)` leading minor
--      of `A` factors as `A 0 0 * det(S_k)` (Schur complement determinant identity
--      applied to the leading submatrix).
-- Combine: `det(A_{k+1}) ≠ 0` (from `hPM`) and `det(A_{k+1}) = A 0 0 * det(S_k)`
-- force `det(S_k) ≠ 0` by field cancellation.
theorem s11324 {n : ℕ} {𝕜 : Type} [Field 𝕜]
    (A : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜)
    (hPM : ∀ k (hk : k ≤ n + 1),
      (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) :
    ∀ k (hk : k ≤ n),
      (Matrix.submatrix
        (fun (i j : Fin n) =>
          A i.succ j.succ - A i.succ 0 * A 0 j.succ / A 0 0)
        (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0  := by
  intro k hk
  have h_a11 : A 0 0 ≠ 0 := a11_ne_zero A hPM
  have h_factor :
      (A.submatrix (Fin.castLE (Nat.succ_le_succ hk))
                   (Fin.castLE (Nat.succ_le_succ hk))).det =
        A 0 0 * (Matrix.submatrix
          (fun (i j : Fin n) =>
            A i.succ j.succ - A i.succ 0 * A 0 j.succ / A 0 0)
          (Fin.castLE hk) (Fin.castLE hk)).det :=
    schur_minor_factor A h_a11 k hk
  have h_total : (A.submatrix (Fin.castLE (Nat.succ_le_succ hk))
                              (Fin.castLE (Nat.succ_le_succ hk))).det ≠ 0 :=
    hPM (k + 1) (Nat.succ_le_succ hk)
  intro h_schur_zero
  apply h_total
  rw [h_factor, h_schur_zero, mul_zero]

end Problems.LinearAlgebra.lu_decomposition
