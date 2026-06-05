import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- inner_tx_eigenvector: ⟪T x, eᵢ⟫ = λᵢ · (repr x i) via symmetry +
-- apply_eigenvectorBasis + inner_smul_right + repr_apply_apply + real_inner_comm
theorem inner_tx_eigenvector
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n)
    (x : E) (i : Fin n) :
    inner ℝ (T x) ((hT.eigenvectorBasis hn) i)
      = hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i := by
  rw [hT x, hT.apply_eigenvectorBasis hn i, inner_smul_right,
      OrthonormalBasis.repr_apply_apply, real_inner_comm]
  simp

end Problems.LinearAlgebra.courant_fischer
