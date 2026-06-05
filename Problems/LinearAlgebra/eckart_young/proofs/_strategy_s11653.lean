import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_finrank_span_top_singular_eigenvectors_2
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_lower_bound_top_singular_span_2

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young, top-(k+1) right-singular subspace.
-- Witness: V = span of the top k+1 eigenvectors of T†T (`isSymmetric_adjoint_comp_self`'s
--   `eigenvectorBasis`, indexed by `Fin.castLE hk` into `Fin (k+1)`).
-- Sub-goal `finrank_span_top_singular_eigenvectors_2`: dim V = k+1 — the k+1 chosen vectors are
--   distinct members of an orthonormal basis, hence linearly independent, so their span has
--   finrank exactly k+1.
-- Sub-goal `norm_lower_bound_top_singular_span_2`: ∀ x ∈ V, σ_k‖x‖ ≤ ‖Tx‖ — the SVD spectral
--   content (T maps each top eigenvector to a singular value ≥ σ_k, descending).
-- Combine: exhibit V as the existential witness, pairing the two facts.
theorem s11653 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  have h_finrank : Module.finrank 𝕜 (Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) = k + 1 :=
    finrank_span_top_singular_eigenvectors_2 T k hk
  have h_bound : ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖ :=
    norm_lower_bound_top_singular_span_2 T k hk
  exact ⟨_, h_finrank, h_bound⟩

end Problems.LinearAlgebra.eckart_young
