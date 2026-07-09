import Library.Geometry.Manifold.ExtDerivCLMSquareZero

/-!
# Boundary operator on currents and the identity $∂^2 = 0$

This file defines the **boundary operator** on de Rham currents over an open subset `Ω`
of a real normed space `E`, and proves that applying it twice yields zero.

## Main definitions

- `Current Ω k`: a $k$-current on `Ω`, i.e., a continuous linear functional on
  `𝓓^∞(Ω, Λ^k)`, the space of smooth compactly-supported test $k$-forms.
- `boundary T`: the boundary of a $(k+1)$-current `T`, defined by duality
  `(∂T)(φ) = T(dφ)`.

## Main statements

- `boundary_boundary_eq_zero`: applying `boundary` twice yields zero,
  i.e., `boundary (boundary T) = 0` for any current `T`.
-/

open Library.Geometry.Manifold.ExtDerivCLMSquareZero
open TestFunction TopologicalSpace
open scoped Distributions ContDiff

namespace Library.Geometry.Currents.BoundarySquareZero

variable {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E] {Ω : Opens E} {k : ℕ}

/-- A **k-current** on an open `Ω ⊆ E`: a continuous linear functional on the
space of smooth compactly-supported test k-forms `𝓓^∞(Ω, Λ^k)`. The de Rham /
Federer-Fleming object that unifies smooth forms and oriented submanifolds. -/
abbrev Current (Ω : Opens E) (k : ℕ) :=
  𝓓^{(⊤ : ℕ∞)}(Ω, E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] ℝ

/-- The **boundary** of a current, defined by duality `(∂T)(φ) = T(dφ)`: precompose
`T` with the exterior-derivative CLM on test forms (`extDerivCLM`, from the
Library). Lowers degree by one. -/
noncomputable def boundary (T : Current Ω (k + 1)) : Current Ω k :=
  T.comp (extDerivCLM k)

/-- **$∂^2 = 0$**: applying the boundary operator twice to any current yields zero,
i.e., `boundary (boundary T) = 0`. This is the distributional analogue of $d^2 = 0$
for differential forms, and follows from `extDerivCLM_comp_extDerivCLM_eq_zero`. -/
theorem boundary_boundary_eq_zero : ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {Ω : Opens E} {k : ℕ} (T : Current Ω (k + 2)),
    boundary (boundary T) = 0 := by
  intro E _ _ Ω k T
  simp only [boundary]
  rw [ContinuousLinearMap.comp_assoc,
    Library.Geometry.Manifold.ExtDerivCLMSquareZero.extDerivCLM_comp_extDerivCLM_eq_zero,
    ContinuousLinearMap.comp_zero]

end Library.Geometry.Currents.BoundarySquareZero
