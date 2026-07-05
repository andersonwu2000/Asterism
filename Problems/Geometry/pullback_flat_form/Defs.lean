import Mathlib
import Library.Geometry.Manifold.DiffFormBundle          -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.AlternatingMapContDiff   -- contdiff_comp_continuous_linear_map_clm

/-!
Setup for the integration-current bridge's first brick: the pullback of a *flat*
test `k`-form `φ` on an ambient normed space `F` along a smooth map `e : N → F`,
as a genuine smooth `k`-form on the manifold-with-boundary `N`.

Unlike the boundary inclusion (`pullbackBdryFun`), whose coordinate derivative is
the *constant* `faceEmbedL`, here the coordinate derivative
`fderivWithin ℝ (e ∘ chartAt.symm) (Set.range 𝓡∂)` varies with the point — the genuine
new ingredient. It must be the one-sided `fderivWithin` over `Set.range 𝓡∂` (not the
two-sided `fderiv`): on `∂N` the chart `.symm` has a `max 0` clamp, so full `fderiv`
is the junk value `0` and discontinuous there (matching the Library convention
`ext_deriv_locality_pullback`).
Its fibrewise smoothness is the proved analytic core
`Library…AlternatingMapContDiff.contdiff_comp_continuous_linear_map_clm`.
-/

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open scoped Manifold Bundle ContDiff

namespace Problems.Geometry.pullback_flat_form

variable {n k : ℕ}
  {N : Type*} [TopologicalSpace N]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) N] [IsManifold (𝓡∂ (n + 1)) ∞ N]
  {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]

/-- Raw fibrewise section of `e* φ`: at `p`, precompose `φ (e p)` (an alternating
`k`-form on `F`) by the coordinate derivative of `e` at `p`, then transport into the
form-bundle fibre over `p`. -/
noncomputable def pullbackFlatFormFun (e : N → F) (φ : F → (F [⋀^Fin k]→L[ℝ] ℝ))
    (p : N) : (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p :=
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin (n + 1)) [⋀^Fin k]→L[ℝ] ℝ)
      (formBundleCore (𝓡∂ (n + 1)) (M := N) k).Fiber p) p
    ((φ (e p)).compContinuousLinearMap
      (fderivWithin ℝ (e ∘ (extChartAt (𝓡∂ (n + 1)) p).symm)
        (Set.range (𝓡∂ (n + 1))) (extChartAt (𝓡∂ (n + 1)) p p)))

end Problems.Geometry.pullback_flat_form
