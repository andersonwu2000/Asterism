import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs._strategy_s11670

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

namespace Problems.Geometry.stokes_bdry_chart

-- chart_right_inv: right inverse law for the boundary chart — faceProj ∘ extChartAt ∘
-- extChartAt.symm ∘ faceEmbed = id on chartTarget, combining PartialEquiv.right_inv
-- with faceEmbed (faceProj w) = w (coord-zero brick s11670).
theorem chart_right_inv : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M), ∀ z ∈ chartTarget p, chartToFun p (chartInvFun p z) = z := by
  intro n M _ _ _ p z hz
  simp only [chartTarget, Set.mem_image] at hz
  obtain ⟨w, ⟨hw_target, hw0⟩, hw_proj⟩ := hz
  simp only [Set.mem_setOf_eq] at hw0
  -- faceEmbed z = w, because faceProj w = z and w 0 = 0
  have hfe : faceEmbed z = w := by
    rw [← hw_proj]; exact s11670 w hw0
  -- therefore faceEmbed z ∈ target
  have hfet : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := hfe.symm ▸ hw_target
  -- unfold chartInvFun: the dite fires on the true branch
  -- reduce chartInvFun on the true branch
  have hinvfun : chartInvFun p z =
      ⟨(extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z),
        faceEmbed_symm_mem_boundary p z hfet⟩ := by
    simp only [chartInvFun, dif_pos hfet]
  rw [hinvfun]
  simp only [chartToFun, faceProj]
  -- right_inv: extChartAt(extChartAt.symm y) = y for y in target
  rw [(extChartAt (𝓡∂ (n + 1)) p.val).right_inv hfet]
  -- faceProj (faceEmbed z) = faceProj w = z
  -- goal is definitionally faceProj w = z
  conv_lhs => rw [hfe]
  exact hw_proj

end Problems.Geometry.stokes_bdry_chart

