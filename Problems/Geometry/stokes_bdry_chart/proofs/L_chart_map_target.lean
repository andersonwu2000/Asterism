import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs._strategy_s11670

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

namespace Problems.Geometry.stokes_bdry_chart

-- chart_map_target: chartInvFun maps chartTarget into chartSource via PartialEquiv.map_target
-- z ∈ chartTarget gives w with faceProj w = z and w ∈ target and w 0 = 0,
-- so faceEmbed z = w by s11670; then map_target gives symm(faceEmbed z) ∈ source.
theorem chart_map_target : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M), ∀ z ∈ chartTarget p, chartInvFun p z ∈ chartSource p := by
  intro n M _ _ _ p z hz
  simp only [chartTarget, Set.mem_image] at hz
  obtain ⟨w, ⟨hw_target, hw_zero⟩, hw_proj⟩ := hz
  simp only [Set.mem_setOf_eq] at hw_zero
  have hw_embed : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    have heq : faceEmbed (faceProj w) = w := s11670 w hw_zero
    rw [← hw_proj, heq]
    exact hw_target
  simp only [chartInvFun, dif_pos hw_embed, chartSource, Set.mem_preimage]
  exact (extChartAt (𝓡∂ (n + 1)) p.val).map_target hw_embed

end Problems.Geometry.stokes_bdry_chart
