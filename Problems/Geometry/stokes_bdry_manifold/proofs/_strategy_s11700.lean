import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs

namespace Problems.Geometry.stokes_bdry_manifold

open scoped Manifold Bundle ContDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBdry.ChartedBdry
open Library.Geometry.ManifoldBdry.BdryChart


-- Direct proof: destruct membership in the transition source into its two defeq components
-- (z ∈ chartTarget p, and chartInvFun p z landing in chartSource q), then translate each via
-- the Library bricks chartTarget_eq_faceEmbed_preimage (target membership of faceEmbed z)
-- and chartInvFun_val_eq_extChartAt_symm_faceEmbed (identifying the inverse chart value with
-- (extChartAt p.val).symm (faceEmbed z)) to land in the extChart coord-change source.
theorem s11700 {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p q : Bdry n M) :
    Set.MapsTo faceEmbed ((bdryChart p).symm ≫ₕ bdryChart q).source
      ((extChartAt (𝓡∂ (n + 1)) p.val).symm ≫ extChartAt (𝓡∂ (n + 1)) q.val).source  := by
  intro z hz
  have hzp : z ∈ chartTarget p := hz.1
  have hzq : (chartInvFun p z).val ∈ (extChartAt (𝓡∂ (n + 1)) q.val).source := hz.2
  have hT : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    rw [chartTarget_eq_faceEmbed_preimage p] at hzp; exact hzp
  refine ⟨hT, ?_⟩
  simp only [PartialEquiv.symm_symm, Set.mem_preimage]
  rw [← chartInvFun_val_eq_extChartAt_symm_faceEmbed p z hzp]
  exact hzq

end Problems.Geometry.stokes_bdry_manifold
