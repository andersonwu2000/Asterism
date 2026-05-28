import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs.L_lu_base
import Problems.LinearAlgebra.lu_decomposition.proofs.L_lu_step

namespace Problems.LinearAlgebra.lu_decomposition

-- Induction on `n`: the parent's universally-quantified statement splits
-- into a vacuous `Fin 0` base case (`lu_base`) and a one-step inductive
-- lift (`lu_step`), combined by `induction n with`.
theorem s11322 : ∀ {n : ℕ} {𝕜 : Type} [Field 𝕜]
    (A : Matrix (Fin n) (Fin n) 𝕜),
    (∀ k (hk : k ≤ n),
      (A.submatrix (Fin.castLE hk) (Fin.castLE hk)).det ≠ 0) →
    ∃ L U : Matrix (Fin n) (Fin n) 𝕜,
      L.BlockTriangular (fun i => (n - 1 : ℕ) - (i : ℕ)) ∧
      U.BlockTriangular (fun i : Fin n => (i : ℕ)) ∧
      (∀ i, L i i = 1) ∧
      A = L * U  := by
  intro n
  induction n with
  | zero => exact lu_base
  | succ n ih => exact lu_step ih

end Problems.LinearAlgebra.lu_decomposition
