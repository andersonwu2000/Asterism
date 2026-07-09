import Library.Geometry.Manifold.DiffFormBundle        -- DiffForm, formBundleCore, instForm*
import Library.Geometry.Manifold.MExtDerivCoord         -- formInCoord, instFormBundleContMDiff
import Library.Geometry.ManifoldBdry.BdryIsManifold      -- instBdryChartedSpace, isManifold_bdry
import Library.Geometry.ManifoldBoundary.CompactBdry     -- Bdry, TopologicalSpace
import Mathlib

open Bundle
open Library.Geometry.Manifold.DiffFormBundle
open Library.Geometry.Manifold.MExtDerivCoord
open Library.Geometry.ManifoldBdry.BdryIsManifold
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.PullbackBdryDefs

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- `dι` of the boundary inclusion in coordinates: the linear face embedding
    `EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n+1))` (coords `1..n`). Since
    `ι` becomes `faceEmbed` (linear) in the charts, `dι` is this constant CLM. -/
noncomputable def faceEmbedL :
    EuclideanSpace ℝ (Fin n) →L[ℝ] EuclideanSpace ℝ (Fin (n + 1)) :=
  ∑ i : Fin n, (EuclideanSpace.proj i).smulRight (EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ)

/-- Raw section of `∂M`'s form bundle for `ι* φ` at `p`: precompose `φ`'s coordinate
    rep at `p.val` by `faceEmbedL` (= `dι`), transport into the `∂M` fibre. -/
noncomputable def pullbackBdryFun (φ : DiffForm (𝓡∂ (n + 1)) M n) (p : Bdry n M) :
    (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p :=
  Trivialization.symmL ℝ
    (trivializationAt (EuclideanSpace ℝ (Fin n) [⋀^Fin n]→L[ℝ] ℝ)
      (formBundleCore (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) (M := Bdry n M) n).Fiber p) p
    (ContinuousAlternatingMap.compContinuousLinearMapCLM faceEmbedL
      (formInCoord (𝓡∂ (n + 1)) φ p.val (extChartAt (𝓡∂ (n + 1)) p.val p.val)))

end Library.Geometry.ManifoldBdry.PullbackBdryDefs
