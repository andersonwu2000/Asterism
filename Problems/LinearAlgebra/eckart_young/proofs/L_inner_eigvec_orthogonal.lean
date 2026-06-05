import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- inner_eigvec_orthogonal: eigenvector bᵢ (i < k) is orthogonal to Kᗮ via Submodule.mem_orthogonal
-- bᵢ lies in the span K of the first k eigenvectors; y ∈ Kᗮ implies ⟪bᵢ, y⟫ = 0.
theorem inner_eigvec_orthogonal {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (y : E) (hy : y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ)
    (i : Fin (Module.finrank 𝕜 E)) (h : (i : ℕ) < k) :
    inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y = 0 := by
  have hb : (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) ∈
      Submodule.span 𝕜 (Set.range (fun j : Fin k =>
        (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl) (Fin.castLE hk.le j))) := by
    apply Submodule.subset_span
    exact ⟨⟨(i : ℕ), h⟩, by congr 1⟩
  exact (Submodule.mem_orthogonal _ _).mp hy _ hb

end Problems.LinearAlgebra.eckart_young
