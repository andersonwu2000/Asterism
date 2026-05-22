import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_exists_b_f_apply_eq_dite_with_zero
import Problems.LinearAlgebra.svd.proofs.L_t_apply_eigenbasis_zero_high

namespace Problems.LinearAlgebra.svd

-- Split into (A) `t_apply_eigenbasis_zero_high`: T(b_E i) = 0 for indices
-- i with (i:ℕ) ≥ finrank F, derived from h_inner (giving ‖T(b_E i)‖² = σ_i²)
-- combined with the rank ≤ codimension bound forcing σ_i = 0 there, and
-- (B) `exists_b_f_apply_eq_dite_with_zero`: the main b_F existence assuming
-- that zero fact as a hypothesis. (A) is a single-equation kernel fact;
-- (B) absorbs all orthonormal-extension construction work and merely uses
-- the zero hypothesis to close the dite "else" branch directly.
theorem s10856 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) =
      if h : (i : ℕ) < (Module.finrank 𝕜 F)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  have h_zero := t_apply_eigenbasis_zero_high T b_E h_inner
  exact exists_b_f_apply_eq_dite_with_zero T b_E h_inner h_zero

end Problems.LinearAlgebra.svd
