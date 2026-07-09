import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDerivCoord         -- formInCoord, instFormBundleContMDiff
import Library.Geometry.Manifold.StokesIntegralDefs      -- OrientedManifold (+ refForm)
import Library.Geometry.ManifoldBdry.BdryIsManifold      -- isManifold_bdry (instance), instBdryChartedSpace
import Library.Geometry.ManifoldBdry.PullbackBdryDefs    -- faceEmbedL
import Library.Geometry.ManifoldBoundary.CompactBdry     -- Bdry
import Mathlib

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.Manifold.StokesIntegralDefs
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBdry.PullbackBdryDefs
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.InducedOrientDefs

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
  [OrientedManifold (𝓡∂ (n + 1)) M]

/-- Chart-local candidate for the induced boundary orientation form, anchored at `q`:
    contract `M`'s reference form `μ` with `-e₀` *in the chart at `q.val`* (`curryLeft`
    fixes the first slot), precompose by `faceEmbedL` (= `dι`), and transport into the
    `∂M` fibre at `p` through the trivialization anchored at `q`. Equals `0` outside
    that trivialization's base set (`symmL` junk value), so it glues by a POU. -/
noncomputable def inducedOrientChartFun (q p : Bdry n M) :
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p :=
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber q) p
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      ((formInCoord (𝓡∂ (n + 1)) (OrientedManifold.refForm (I := 𝓡∂ (n + 1)) (N := M))
          q.val (extChartAt (𝓡∂ (n + 1)) q.val p.val)).curryLeft
            (-EuclideanSpace.basisFun (Fin (n + 1)) ℝ 0)))

variable (n M) in
/-- A chosen smooth partition of unity on `∂M` subordinate to the chart sources. -/
noncomputable def inducedOrientPOU
    [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)] :
    SmoothPartitionOfUnity (Bdry n M) 𝓘(ℝ, EuclideanSpace ℝ (Fin n)) (Bdry n M) :=
  (SmoothPartitionOfUnity.exists_isSubordinate_chartAt_source
    (M := Bdry n M) (I := 𝓘(ℝ, EuclideanSpace ℝ (Fin n)))).choose

/-- The induced boundary orientation's reference form `ι_ν μ` at `p`: the POU-glued
    combination of the chart-local candidates. Chart-independent by construction; this
    is the boundary orientation Stokes' sign convention selects (each candidate, hence
    the glue, lies on the same positive ray at every point). -/
noncomputable def inducedOrientFun
    [T2Space (Bdry n M)] [SigmaCompactSpace (Bdry n M)] (p : Bdry n M) :
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p :=
  ∑ᶠ q : Bdry n M, inducedOrientPOU n M q p • inducedOrientChartFun q p

end Library.Geometry.Manifold.InducedOrientDefs
