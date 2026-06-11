import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Geometry.Manifold.VectorBundle.Tangent

/-!
# Coordinate change for differential forms on a manifold

This file defines the coordinate-change map for exterior power bundles `⋀ᵏ T*M`
and proves the cocycle condition: consecutive transitions compose correctly.

## Main definitions

- `formCoordChange`: the fibre-wise coordinate-change map for `k`-forms.

## Main statements

- `formCoordChange_comp`: the cocycle identity
  `formCoordChange j l ∘ formCoordChange i j = formCoordChange i l`.
-/

open Bundle
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.FormCoordChange

variable
  {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
  {H : Type*} [TopologicalSpace H]
  (I : ModelWithCorners ℝ E H)
  {M : Type*} [TopologicalSpace M] [ChartedSpace H M] [IsManifold I ∞ M]

/-- Transition map of `⋀ᵏ T*M`: precompose alternating maps by the (swapped)
tangent transition. -/
noncomputable def formCoordChange (k : ℕ) (i j : atlas H M) (x : M) :
    (E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ] (E [⋀^Fin k]→L[ℝ] ℝ) :=
  ContinuousAlternatingMap.compContinuousLinearMapCLM
    ((tangentBundleCore I M).coordChange j i x)

/-- The cocycle identity for `formCoordChange`: on the triple intersection of base sets,
composing the transition from `i` to `j` followed by `j` to `l` equals the direct
transition from `i` to `l`. -/
theorem formCoordChange_comp (k : ℕ) (i j l : atlas H M) :
    ∀ x ∈ (tangentBundleCore I M).baseSet i ∩ (tangentBundleCore I M).baseSet j
        ∩ (tangentBundleCore I M).baseSet l, ∀ v,
      formCoordChange I k j l x (formCoordChange I k i j x v)
        = formCoordChange I k i l x v := by
  intro x hx v
  obtain ⟨⟨hi, hj⟩, hl⟩ := hx
  ext m
  simp only [formCoordChange,
    ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousAlternatingMap.compContinuousLinearMap_apply]
  congr 1
  funext u
  simp only [Function.comp_apply]
  exact (tangentBundleCore I M).coordChange_comp l j i x ⟨⟨hl, hj⟩, hi⟩ (m u)

end Library.Geometry.Manifold.FormCoordChange
