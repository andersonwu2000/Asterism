import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_inner_tx_eigenvector

namespace Problems.LinearAlgebra.courant_fischer

-- Rayleigh numerator in the eigenbasis: expand ⟪Tx,x⟫ over the orthonormal
-- eigenbasis via `sum_inner_mul_inner`; each cross term ⟪Tx,bᵢ⟫·⟪bᵢ,x⟫ reduces
-- (sub-goal `inner_Tx_eigenvector`) to λᵢ·(repr x i), giving λᵢ·(repr x i)².
theorem s11614
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    inner ℝ (T x) x =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2  := by
  have hA := fun i => inner_tx_eigenvector hT hn x i
  rw [← OrthonormalBasis.sum_inner_mul_inner (hT.eigenvectorBasis hn) (T x) x]
  apply Finset.sum_congr rfl
  intro i _
  rw [hA i, OrthonormalBasis.repr_apply_apply]
  ring

end Problems.LinearAlgebra.courant_fischer
