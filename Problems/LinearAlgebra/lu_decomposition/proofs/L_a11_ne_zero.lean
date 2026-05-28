import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs

namespace Problems.LinearAlgebra.lu_decomposition

-- a11_ne_zero: pivot A 0 0 ≠ 0 from the k=1 leading-principal-minor hypothesis via det_fin_one
-- entry_kind: Builder
theorem a11_ne_zero {n : ℕ} {𝕜 : Type} [Field 𝕜]
    (A : Matrix (Fin (n + 1)) (Fin (n + 1)) 𝕜)
    (hPM : ∀ k (hk : k ≤ n + 1),
      (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) :
    A 0 0 ≠ 0 := by
  have h1 : 1 ≤ n + 1 := Nat.succ_le_succ (Nat.zero_le n)
  have hd := hPM 1 h1
  rw [Matrix.det_fin_one] at hd
  exact hd

end Problems.LinearAlgebra.lu_decomposition
