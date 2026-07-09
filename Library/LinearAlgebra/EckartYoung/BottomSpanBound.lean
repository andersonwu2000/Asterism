import Library.LinearAlgebra.EckartYoung.EigenExpansion
import Library.LinearAlgebra.EckartYoung.SingularEigenRelations
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.InnerProductSpace.Projection.Basic
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Data.Fin.Basic
import Mathlib.LinearAlgebra.FiniteDimensional.Basic
import Mathlib.Tactic

/-!
# Norm bounds on the bottom singular subspace

This file establishes norm bounds for a linear map `T : E →ₗ[𝕜] F` when restricted
to the orthogonal complement of the span of its top-`k` right singular vectors.

## Main statements

* `norm_sub_starprojection_le`: the orthogonal complement projection is a contraction,
  i.e., `‖x - K.starProjection x‖ ≤ ‖x‖` for any submodule `K`.
* `bottom_span_norm_sq_le`: on the orthogonal complement of the span of the top-`k`
  right singular vectors, the squared norm satisfies `‖T y‖² ≤ σ_k² · ‖y‖²`.
* `bottom_span_norm_le`: the norm version, `‖T y‖ ≤ σ_k · ‖y‖`, lifted from the
  squared bound.
-/

open Library.LinearAlgebra.EckartYoung.EigenExpansion
open Library.LinearAlgebra.EckartYoung.SingularEigenRelations

namespace Library.LinearAlgebra.EckartYoung.BottomSpanBound

/-- The orthogonal projection onto a submodule `K` is a contraction: the residual
`x - K.starProjection x` satisfies `‖x - K.starProjection x‖ ≤ ‖x‖`. This follows
from the Pythagorean identity `orthogonalProjectionFn_norm_sq`. -/
theorem norm_sub_starprojection_le {𝕜 : Type*} [RCLike 𝕜]
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (K : Submodule 𝕜 E) (x : E) :
    ‖x - K.starProjection x‖ ≤ ‖x‖ := by
  have hpy := K.orthogonalProjectionFn_norm_sq x
  simp only [Submodule.orthogonalProjectionFn_eq, Submodule.coe_orthogonalProjection_apply] at hpy
  nlinarith [norm_nonneg x, norm_nonneg (x - K.starProjection x), norm_nonneg (K.starProjection x)]

/-- On the orthogonal complement of the span of the top-`k` right singular vectors of `T`,
the squared operator norm satisfies `‖T y‖² ≤ σ_k² · ‖y‖²`.

The proof expands `‖T y‖²` in the eigenbasis of `T†T` via `norm_sq_eq_sum_eigen`,
then bounds each summand termwise using `termwise_le_singular_k` — the bound vanishes
for indices `i < k` because `y` is orthogonal to `K`, and `λ_i ≤ σ_k²` holds for
`i ≥ k` by antitonicity of singular values. Finally, `sum_sq_norm_inner_right` collapses
`σ_k² · ∑ ‖⟨bᵢ, y⟩‖²` to `σ_k² · ‖y‖²`. -/
theorem bottom_span_norm_sq_le {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ,
      ‖T y‖ ^ 2 ≤ (T.singularValues k) ^ 2 * ‖y‖ ^ 2  := by
  intro y hy
  have h_eq := norm_sq_eq_sum_eigen T y
  rw [h_eq,
      ← (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)).sum_sq_norm_inner_right y,
      Finset.mul_sum]
  exact Finset.sum_le_sum (fun i _ => termwise_le_singular_k T k hk y hy i)

/-- On the orthogonal complement of the span of the top-`k` right singular vectors of `T`,
the operator satisfies `‖T y‖ ≤ σ_k · ‖y‖`.

This is the norm version of `bottom_span_norm_sq_le`: we lift the squared bound
`‖T y‖² ≤ (σ_k · ‖y‖)²` to the linear bound via `le_of_sq_le_sq`, using
nonnegativity of `σ_k · ‖y‖`. -/
theorem bottom_span_norm_le {𝕜 : Type*} [RCLike 𝕜]
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

end Library.LinearAlgebra.EckartYoung.BottomSpanBound
