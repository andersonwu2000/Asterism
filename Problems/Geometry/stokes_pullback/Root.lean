-- §A.7: `pullbackBdryFun φ` is a `C^∞` section of `⋀ⁿ T*∂M` — the smoothness witness
-- for `ι* φ`. Stated as the explicit `ContMDiff` of the total-space map (fibre family
-- pinned by `(E := …)`), mirroring P5's `mextDeriv` smoothness Root so the `∂M`
-- fibre-bundle + smooth-bundle instances resolve. P12 assembles
-- `pullbackBdry := ⟨pullbackBdryFun, this⟩`.
import Mathlib
import Problems.Geometry.stokes_pullback.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBdry.BdryIsManifold

namespace Problems.Geometry.stokes_pullback

-- `∂M`'s `IsManifold` is a global `@[instance]` (P9 `isManifold_bdry`), found directly.

theorem main : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (φ : DiffForm (𝓡∂ (n + 1)) M n),
    ContMDiff (𝓘(ℝ, EuclideanSpace ℝ (Fin n)))
        ((𝓘(ℝ, EuclideanSpace ℝ (Fin n))).prod
          𝓘(ℝ, EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)) ∞
      (fun p => Bundle.TotalSpace.mk'
        (E := fun q => (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q)
        (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ) p (pullbackBdryFun φ p)) := by
  sorry

end Problems.Geometry.stokes_pullback
