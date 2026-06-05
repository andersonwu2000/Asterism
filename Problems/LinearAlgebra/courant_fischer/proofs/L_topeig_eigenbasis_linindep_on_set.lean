import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- topeig_eigenbasis_linindep_on_set: linear independence of eigenvectorBasis restricted to {i ≤ k}
-- via orthonormality: eigenvectorBasis is orthonormal, any subfamily (injective reindex) is too

theorem topeig_eigenbasis_linindep_on_set
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    LinearIndependent ℝ
      (fun i : ↥{i : Fin n | (i : ℕ) ≤ (k : ℕ)} => (hT.eigenvectorBasis hn) (i : Fin n)) := by
  apply Orthonormal.linearIndependent
  exact (hT.eigenvectorBasis hn).orthonormal.comp _ Subtype.val_injective

end Problems.LinearAlgebra.courant_fischer

