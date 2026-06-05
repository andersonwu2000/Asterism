import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_finrank_span_top_singular_eigenvectors
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_lower_bound_top_singular_span

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young lower bound, spectral half: build the top-(k+1) right-singular subspace.
-- `V` is the span of the first k+1 eigenvectors of `T† ∘ₗ T` (sorted by decreasing
-- eigenvalue σ_i²), supplied by `hT.eigenvectorBasis`. The goal's two conjuncts split into
-- two independent, strictly-smaller obligations on this fixed `V`:
--   `finrank_span_top_singular_eigenvectors` — `V` has dimension exactly k+1 (k+1 vectors
--     drawn from an orthonormal basis are linearly independent);
--   `norm_lower_bound_top_singular_span` — on `V`, `σ_k‖x‖ ≤ ‖T x‖` (the spectral content:
--     every eigenvalue contributing to `x` is ≥ σ_k²).
-- Combinator: `refine ⟨V, ?_, ?_⟩` then discharge each conjunct by its sub-goal.
theorem s11650 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖ := by
  classical
  refine ⟨Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
    (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
      (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))), ?_, ?_⟩
  · exact finrank_span_top_singular_eigenvectors T k hk
  · exact norm_lower_bound_top_singular_span T k hk

end Problems.LinearAlgebra.eckart_young
