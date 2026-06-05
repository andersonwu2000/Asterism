import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_nonzero_mem_inf_of_finrank
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_top_singular_subspace
import Problems.LinearAlgebra.eckart_young.proofs.L_ker_finrank_ge

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young lower bound: a kernel vector of S on which T cannot shrink below σ_k.
-- `exists_top_singular_subspace` builds the (k+1)-dim top right-singular span V on which
-- `σ_k‖x‖ ≤ ‖T x‖` holds (the spectral content). `ker_finrank_ge` gives
-- `finrank E ≤ finrank(ker S) + k` (rank–nullity). Since
-- `finrank V + finrank(ker S) = (k+1) + finrank(ker S) > finrank E`, the 𝕜-version
-- `exists_nonzero_mem_inf_of_finrank` (dimension-count intersection) yields a nonzero
-- `x ∈ V ∩ ker S`; `S x = 0` from `mem_ker`, `σ_k‖x‖ ≤ ‖T x‖` from V's bound.
theorem s11647 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (S : E →ₗ[𝕜] F) (k : ℕ)
    (hk : k < Module.finrank 𝕜 E)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k) :
    ∃ x : E, x ≠ 0 ∧ S x = 0 ∧ T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  obtain ⟨V, hVdim, hVbound⟩ := exists_top_singular_subspace T k hk
  have hker : Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k :=
    ker_finrank_ge S k hrank
  obtain ⟨x, hxV, hxker, hxne⟩ :=
    exists_nonzero_mem_inf_of_finrank V (LinearMap.ker S) (by rw [hVdim]; omega)
  exact ⟨x, hxne, LinearMap.mem_ker.mp hxker, hVbound x hxV⟩

end Problems.LinearAlgebra.eckart_young
