import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_nonzero_mem_inf_of_finrank_2
import Problems.LinearAlgebra.eckart_young.proofs.L_top_singular_subspace_bound

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young lower bound, kernel witness: a nonzero x killed by S with σ_k‖x‖ ≤ ‖T x‖.
-- Sub-goal `top_singular_subspace_bound`: the top-(k+1) right-singular span V (dim k+1)
--   on which T is bounded below by σ_k (the SVD content).
-- Rank–nullity (`finrank_range_add_finrank_ker`) gives dim(ker S) ≥ n−k inline, so
--   dim V + dim(ker S) ≥ (k+1)+(n−k) > n; sub-goal `exists_nonzero_mem_inf_of_finrank_2`
--   (abstract dimension-counting) yields a nonzero x ∈ V ∩ ker S. Then S x = 0 and the
--   V-bound give the conclusion.
theorem s11651 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (S : E →ₗ[𝕜] F)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k)
    (hk : k < Module.finrank 𝕜 E) :
    ∃ x : E, x ≠ 0 ∧ S x = 0 ∧ T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  have h_top : ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖ := top_singular_subspace_bound T k hk
  have h_ker : Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k := by
    have h := S.finrank_range_add_finrank_ker (K := 𝕜)
    omega
  obtain ⟨V, hVdim, hVbound⟩ := h_top
  have hcount : Module.finrank 𝕜 E < Module.finrank 𝕜 V + Module.finrank 𝕜 (LinearMap.ker S) := by
    rw [hVdim]; omega
  obtain ⟨x, hxV, hxker, hx0⟩ := exists_nonzero_mem_inf_of_finrank_2 V (LinearMap.ker S) hcount
  exact ⟨x, hx0, LinearMap.mem_ker.mp hxker, hVbound x hxV⟩

end Problems.LinearAlgebra.eckart_young
