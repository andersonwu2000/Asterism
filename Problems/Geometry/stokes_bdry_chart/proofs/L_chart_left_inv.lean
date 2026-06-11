import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs
import Problems.Geometry.stokes_bdry_chart.proofs.L_boundary_mem_frontier_target
import Problems.Geometry.stokes_bdry_chart.proofs.L_frontier_range_of_frontier_target
import Problems.Geometry.stokes_bdry_chart.proofs.L_coord_zero_of_frontier_range
import Problems.Geometry.stokes_bdry_chart.proofs._strategy_s11670

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

namespace Problems.Geometry.stokes_bdry_chart

-- chart_left_inv: bricks B+C + PartialEquiv.left_inv + Subtype.ext
-- brick C: boundary_ext_chart_at_coord_zero gives extChartAt q 0 = 0;
-- brick B: s11670 gives faceEmbed(faceProj w)=w when w 0=0;
-- together they reduce chartInvFun(chartToFun q) to extChartAt.symm(extChartAt q)=q.
theorem chart_left_inv : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p : Bdry n M), ∀ q ∈ chartSource p, chartInvFun p (chartToFun p q) = q := by
  intro n M _ _ _ p q hq
  simp only [chartSource, Set.mem_preimage] at hq
  have htarget : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      (extChartAt (𝓡∂ (n + 1)) p.val).target :=
    (extChartAt (𝓡∂ (n + 1)) p.val).map_source hq
  have hbd' : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      frontier (extChartAt (𝓡∂ (n + 1)) p.val).target :=
    boundary_mem_frontier_target p.val q.val hq q.2
  have hfr : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈ frontier (Set.range (𝓡∂ (n + 1))) :=
    frontier_range_of_frontier_target p.val _ htarget hbd'
  have hcoord0 : extChartAt (𝓡∂ (n + 1)) p.val q.val 0 = 0 :=
    coord_zero_of_frontier_range _ hfr
  have hfep : faceEmbed (faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val)) =
      extChartAt (𝓡∂ (n + 1)) p.val q.val :=
    s11670 _ hcoord0
  have h_in : faceEmbed (faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val)) ∈
      (extChartAt (𝓡∂ (n + 1)) p.val).target := by rw [hfep]; exact htarget
  simp only [chartInvFun, chartToFun]
  rw [dif_pos h_in]
  apply Subtype.ext
  simp only [hfep]
  exact (extChartAt (𝓡∂ (n + 1)) p.val).left_inv hq

end Problems.Geometry.stokes_bdry_chart
