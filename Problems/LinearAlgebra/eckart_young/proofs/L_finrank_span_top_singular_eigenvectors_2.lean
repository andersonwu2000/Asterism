import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- finrank_span_top_singular_eigenvectors_2: finrank_span_eq_card + Orthonormal.linearIndependent
-- Identical statement to finrank_span_top_singular_eigenvectors; same proof applies.
theorem finrank_span_top_singular_eigenvectors_2 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    Module.finrank 𝕜 (Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) = k + 1 := by
  let hb := T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl
  have hli : LinearIndependent 𝕜 (fun i : Fin (k + 1) => hb (Fin.castLE hk i)) :=
    hb.orthonormal.linearIndependent.comp _ (Fin.castLE_injective _)
  rw [finrank_span_eq_card hli, Fintype.card_fin]

end Problems.LinearAlgebra.eckart_young

