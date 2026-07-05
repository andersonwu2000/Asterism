import Mathlib
import Library.Geometry.Manifold.ExtDerivCLMSquareZero

open scoped Distributions ContDiff
open TestFunction TopologicalSpace
open Library.Geometry.Manifold.ExtDerivCLMSquareZero

namespace Problems.Geometry.currents_boundary_zero

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

end Problems.Geometry.currents_boundary_zero
