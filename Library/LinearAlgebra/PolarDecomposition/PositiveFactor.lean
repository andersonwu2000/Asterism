import Library.LinearAlgebra.PolarDecomposition.Basic
import Mathlib

open Library.LinearAlgebra.PolarDecomposition.Basic

namespace Library.LinearAlgebra.PolarDecomposition.PositiveFactor

-- Quadratic form of the diagonal operator P = constr(σ_i • b_E i) on the orthonormal basis b_E.
-- h1: expand P x via constr into ∑ ⟪b_E i, x⟫ • (σ_i • b_E i) (drops the constr abstraction).
-- h2: evaluate ⟪·, x⟫ on that sum; orthonormality collapses it to ∑ σ_i • ‖⟪b_E i, x⟫‖² in 𝕜.
-- h3: push RCLike.re through the sum and the real-scalar products to the final real sum.
theorem p_inner_re_eq_sum {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  RCLike.re (inner 𝕜 ((b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)) x) x)
    = ∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * ‖(inner 𝕜 (b_E i) x : 𝕜)‖^2  := by
  have h1 := p_constr_apply_eq_sum T b_E x
  have h2 := inner_diag_sum_eq_weighted T b_E x
  have h3 := re_sum_weighted_eq_real_sum T b_E x
  rw [h1, h2]; exact h3

-- `P.IsSymmetric ↔ (P.toMatrix b_E b_E).IsHermitian` for an orthonormal basis
-- (`LinearMap.isHermitian_toMatrix_iff`); rewrite into the concrete matrix world,
-- where the matrix of the diagonal map P : b_E i ↦ σ_i • b_E i is diagonal with real
-- entries σ_i, hence Hermitian — a finite, computational `ext`-check, strictly more
-- concrete than the inner-product symmetry statement.
theorem p_symmetric {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E) :
  (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).IsSymmetric  := by
  rw [← LinearMap.isHermitian_toMatrix_iff b_E]
  exact p_matrix_hermitian T b_E

-- P : b_E i ↦ σ_i • b_E i is the diagonal operator; show 0 ≤ re ⟪P x, x⟫.
-- Expand the quadratic form on the orthonormal basis (p_inner_re_eq_sum) into the
-- real sum ∑ σ_i ‖⟪b_E i, x⟫‖², then conclude termwise from σ_i ≥ 0
-- (p_sum_sigma_norm_nonneg). Both halves drop the inner-product over a 𝕜-linear map.
theorem p_inner_nonneg {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E) :
  ∀ x, 0 ≤ RCLike.re (inner 𝕜
    ((b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)) x) x)  := by
  intro x
  have h1 := p_inner_re_eq_sum T b_E x
  have h2 := p_sum_sigma_norm_nonneg T b_E x
  rw [h1]; exact h2

-- Decompose `P.IsPositive` for the diagonal operator P : b_E i ↦ σ_i • b_E i.
-- `LinearMap.IsPositive` unfolds to `IsSymmetric P ∧ ∀ x, 0 ≤ re ⟪P x, x⟫`; split into
-- the two independent halves and recombine with the anonymous constructor ⟨·, ·⟩.
-- Both sub-goals are strictly simpler than positivity:
--  • p_symmetric: ⟪P x, y⟫ = ⟪x, P y⟫ — the diagonal entries σ_i are real, so P is
--    self-adjoint; reduces to a basis-coordinate computation.
--  • p_inner_nonneg: 0 ≤ re ⟪P x, x⟫ — expands to ∑ σ_i ‖⟪x, b_E i⟫‖² ≥ 0 using
--    σ_i ≥ 0 (LinearMap.singularValues_nonneg).
theorem p_is_positive : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E),
  (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).IsPositive  := by
  intro 𝕜 _ E _ _ _ T b_E
  have h_sym := p_symmetric T b_E
  have h_nonneg := p_inner_nonneg T b_E
  exact ⟨h_sym, h_nonneg⟩

end Library.LinearAlgebra.PolarDecomposition.PositiveFactor
