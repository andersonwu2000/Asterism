import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs

namespace Problems.Geometry.stokes_bdry_manifold

open scoped Manifold ContDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBdry.ChartedBdry
open Library.Geometry.ManifoldBdry.BdryChart

-- Direct proof: the transition is definitionally `chartToFun q ∘ chartInvFun p`; on the
-- transition source `z ∈ chartTarget p`, so the Library lemma
-- `chartInvFun_val_eq_extChartAt_symm_faceEmbed` rewrites the inner point to
-- `(extChartAt p.val).symm (faceEmbed z)`, after which both sides agree by `rfl`.
theorem s11701 {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p q : Bdry n M) :
    ∀ z ∈ ((bdryChart p).symm ≫ₕ bdryChart q).source,
      ((bdryChart p).symm ≫ₕ bdryChart q) z =
        faceProj ((extChartAt (𝓡∂ (n + 1)) q.val ∘
          (extChartAt (𝓡∂ (n + 1)) p.val).symm) (faceEmbed z))  := by
  intro z hz
  have hz_tgt : z ∈ chartTarget p := hz.1
  have hval := chartInvFun_val_eq_extChartAt_symm_faceEmbed p z hz_tgt
  change chartToFun q (chartInvFun p z) = _
  unfold chartToFun
  rw [hval]
  rfl


end Problems.Geometry.stokes_bdry_manifold

