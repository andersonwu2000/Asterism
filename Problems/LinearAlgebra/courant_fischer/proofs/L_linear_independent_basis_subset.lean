import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- linear_independent_basis_subset: orthonormal basis restriction to {i : Fin n // m ≤ i} is
-- linearly independent — orthonormality of the subfamily (injective reindex) gives linear indep.
theorem linear_independent_basis_subset
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    LinearIndependent ℝ (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) := by
  apply Orthonormal.linearIndependent
  exact b.orthonormal.comp _ Subtype.val_injective

end Problems.LinearAlgebra.courant_fischer

