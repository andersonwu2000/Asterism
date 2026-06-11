/-
  Defs.lean — shared vocabulary for the `formCoordChange_continuousOn` obligation
  (§A.2 of the Stokes form-bundle construction). Just the genuine, sorry-free
  `formCoordChange` data def; the lemma to prove is the Root.
-/
import Mathlib

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_form_coord_cont

section FormBundle

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

end FormBundle

end Problems.Geometry.stokes_form_coord_cont
