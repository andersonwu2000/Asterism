import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_finrank_span_image_high
import Problems.LinearAlgebra.courant_fischer.proofs.L_inner_eq_zero_of_mem_span_high

namespace Problems.LinearAlgebra.courant_fischer

-- Construct W as the span of the bottom eigenvectors {bᵢ : k ≤ i}, abstracting
-- the eigenvector basis to a generic orthonormal basis `b`.
-- finrank_span_image_high: |{i : k ≤ i}| = n−k gives the dimension count.
-- inner_eq_zero_of_mem_span_high: orthonormality kills ⟪bᵢ, x⟫ for i<k (x ∈ bottom modes).

theorem s11625
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ W : Submodule ℝ E, Module.finrank ℝ W = n - (k : ℕ) ∧
      ∀ x : E, x ∈ W → ∀ i : Fin n, (i : ℕ) < (k : ℕ) →
        @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0  := by
  set b := hT.eigenvectorBasis hn with hb
  refine ⟨Submodule.span ℝ (b '' {i : Fin n | (k : ℕ) ≤ (i : ℕ)}), ?_, ?_⟩
  · exact finrank_span_image_high b (k : ℕ)
  · exact inner_eq_zero_of_mem_span_high b (k : ℕ)

end Problems.LinearAlgebra.courant_fischer
