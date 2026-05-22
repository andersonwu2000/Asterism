import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_singular_values_zero_high
import Problems.LinearAlgebra.svd.proofs.L_t_apply_zero_of_singular_zero

namespace Problems.LinearAlgebra.svd

-- Split into (A) `singular_values_zero_high`: a pure singular-value fact —
-- T.singularValues i = 0 once i ≥ finrank F (rank ≤ codim + antitone),
-- independent of b_E / h_inner; and (B) `t_apply_zero_of_singular_zero`:
-- given that σ_i = 0 and the diagonal inner-product identity from h_inner,
-- conclude T (b_E i) = 0 via ‖T (b_E i)‖² = σ_i² = 0.
theorem s10857 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∀ (i : Fin (Module.finrank 𝕜 E)),
  ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner i hi
  have hge : Module.finrank 𝕜 F ≤ (i : ℕ) := not_lt.mp hi
  have h_sigma_zero : T.singularValues (i : ℕ) = 0 :=
    singular_values_zero_high T (i : ℕ) hge
  exact t_apply_zero_of_singular_zero T b_E h_inner i h_sigma_zero

end Problems.LinearAlgebra.svd
