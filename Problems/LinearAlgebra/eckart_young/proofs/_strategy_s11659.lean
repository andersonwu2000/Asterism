import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_bottom_span_norm_sq_le

namespace Problems.LinearAlgebra.eckart_young

-- On `Kᗮ` (K = span of the top-k right singular vectors of `T`), `T` shrinks by `σ_k`.
-- Reduce to the squared bound `‖T y‖² ≤ σ_k² ‖y‖²` (the inner-product / eigenvalue content,
-- delegated to `bottom_span_norm_sq_le`), then lift through `le_of_sq_le_sq` since both
-- `σ_k * ‖y‖` and the norms are nonnegative.
theorem s11659 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ,
      ‖T y‖ ≤ T.singularValues k * ‖y‖  := by
  intro y hy
  have hsq : ‖T y‖ ^ 2 ≤ (T.singularValues k * ‖y‖) ^ 2 := by
    rw [mul_pow]
    exact bottom_span_norm_sq_le T k hk y hy
  exact le_of_sq_le_sq hsq (mul_nonneg (T.singularValues_nonneg k) (norm_nonneg _))

end Problems.LinearAlgebra.eckart_young
