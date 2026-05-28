import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs

namespace Problems.LinearAlgebra.lu_decomposition

-- entry_kind: Builder
-- lu_base: base case n=0; all conditions vacuously hold on the empty Fin 0 matrix
theorem lu_base : ∀ {𝕜 : Type} [Field 𝕜] (A : Matrix (Fin 0) (Fin 0) 𝕜),
    (∀ k (hk : k ≤ 0),
      (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) →
    ∃ L U : Matrix (Fin 0) (Fin 0) 𝕜,
      (L.BlockTriangular fun i : Fin 0 => (0 - 1 : ℕ) - (i : ℕ)) ∧
      (U.BlockTriangular fun i : Fin 0 => (i : ℕ)) ∧
      (∀ i, L i i = 1) ∧
      A = L * U := by
  intro 𝕜 _ A _
  refine ⟨1, 1, fun i _ _ => Fin.elim0 i, fun i _ _ => Fin.elim0 i,
    fun i => Fin.elim0 i, ?_⟩
  ext i
  exact Fin.elim0 i

end Problems.LinearAlgebra.lu_decomposition
