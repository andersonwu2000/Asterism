import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_numerator_eigenbasis

namespace Problems.LinearAlgebra.courant_fischer

theorem numerator_eigenbasis_expand
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E] [FiniteDimensional ℝ E]
    {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank ℝ E = n) (x : E) :
    (inner ℝ (T x) x : ℝ) =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 := by apply rayleigh_numerator_eigenbasis <;> assumption

end Problems.LinearAlgebra.courant_fischer
