import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Data.Finsupp.Basic
import Mathlib.LinearAlgebra.Dimension.Finrank
import Mathlib.LinearAlgebra.FiniteDimensional.Basic

/-!
# Singular value vanishing results

This file collects auxiliary lemmas showing that `LinearMap.singularValues` vanishes beyond the
codimension of the map, and that a basis vector maps to zero whenever the corresponding singular
value is zero.

## Main statements

- `singular_values_zero_high`: `T.singularValues i = 0` whenever `Module.finrank 𝕜 F ≤ i`.
- `t_apply_zero_of_singular_zero`: given the diagonal inner-product identity for a basis `b_E`,
  `T.singularValues (↑i) = 0` implies `T (b_E i) = 0`.
- `apply_basis_eq_zero_of_singularValues_zero`: corollary restating the above with a real-valued
  singular value.
- `apply_basis_eq_zero_of_not_lt_finrank`: if `¬ (↑i < Module.finrank 𝕜 F)` then
  `T (b_E i) = 0`.
-/

namespace Library.LinearAlgebra.SVD.SingularValues

/-- `T.singularValues i = 0` for all indices `i ≥ Module.finrank 𝕜 F`.

The support of `T.singularValues` equals `Finset.range (Module.finrank 𝕜 T.range)`, and
`Module.finrank 𝕜 T.range ≤ Module.finrank 𝕜 F` by `Submodule.finrank_le`, so any index
at or beyond the codimension gives zero. -/
theorem singular_values_zero_high : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F)
    (i : ℕ), Module.finrank 𝕜 F ≤ i → T.singularValues i = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T i hi
  have hsupp : T.singularValues.support = Finset.range (Module.finrank 𝕜 T.range) :=
    LinearMap.support_singularValues T
  have hrange : Module.finrank 𝕜 T.range ≤ Module.finrank 𝕜 F :=
    Submodule.finrank_le T.range
  have hni : i ∉ T.singularValues.support := by
    rw [hsupp]
    simp only [Finset.mem_range, not_lt]
    exact le_trans hrange hi
  simp only [Finsupp.mem_support_iff, ne_eq, not_not] at hni
  exact hni

/-- If `T.singularValues (↑i) = 0` and the inner-product identity
`⟪T (b_E i), T (b_E j)⟫_𝕜 = if i = j then ((T.singularValues i : ℝ) ^ 2 : 𝕜) else 0`
holds, then `T (b_E i) = 0`.

The diagonal case gives `⟪T (b_E i), T (b_E i)⟫_𝕜 = σ_i ^ 2 = 0`, so `T (b_E i) = 0`
by `inner_self_eq_zero`. -/
theorem t_apply_zero_of_singular_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F)
    (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
    (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
      if i = j then (((T.singularValues i : ℝ) ^ 2 : 𝕜)) else 0)
    (i : Fin (Module.finrank 𝕜 E)),
    T.singularValues (i : ℕ) = 0 → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner i h_zero
  have hii := h_inner i i
  simp only [↓reduceIte] at hii
  rw [h_zero] at hii
  simp only [ne_eq, OfNat.ofNat_ne_zero, not_false_eq_true, zero_pow, RCLike.ofReal_zero] at hii
  exact inner_self_eq_zero.mp hii

/-- If `(T.singularValues ↑i : ℝ) = 0`, then `T (b_E i) = 0`.

A corollary of `t_apply_zero_of_singular_zero`. The hypothesis `_h_zero` (providing vanishing
on indices beyond `finrank F` via a separate route) is not needed here. -/
theorem apply_basis_eq_zero_of_singularValues_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F)
    (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
    (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
      if i = j then (((T.singularValues i : ℝ) ^ 2 : 𝕜)) else 0)
    (_h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
      ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
    ∀ (i : Fin (Module.finrank 𝕜 E)),
      (T.singularValues i : ℝ) = 0 → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner _h_zero i hi
  exact t_apply_zero_of_singular_zero T b_E h_inner i hi

/-- If `¬ ((↑i : ℕ) < Module.finrank 𝕜 F)`, then `T (b_E i) = 0`.

Combines `singular_values_zero_high` (the index is beyond the codimension, so the singular value
vanishes) with `t_apply_zero_of_singular_zero` (a zero singular value implies a zero image). -/
theorem apply_basis_eq_zero_of_not_lt_finrank : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F)
    (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
    (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
      if i = j then (((T.singularValues i : ℝ) ^ 2 : 𝕜)) else 0),
    ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner i hi
  exact t_apply_zero_of_singular_zero T b_E h_inner i
    (singular_values_zero_high T i.val (not_lt.mp hi))

end Library.LinearAlgebra.SVD.SingularValues
