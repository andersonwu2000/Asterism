import Mathlib
import Problems.Geometry.stokes_bdry_chart.Defs

open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_chart

-- frontier_range_of_frontier_target: converse of frontier_target_of_frontier_range;
-- frontier of extChartAt target implies frontier of model range, via frontier_inter_open_inter.
theorem frontier_range_of_frontier_target {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target)
    (hft : y ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target) :
    y ∈ frontier (Set.range (𝓡∂ (n + 1))) := by
  rw [extChartAt_target] at hy hft
  have ht : IsOpen ((𝓡∂ (n + 1)).symm ⁻¹'
      (chartAt (EuclideanHalfSpace (n + 1)) x).target) :=
    (chartAt _ x).open_target.preimage (𝓡∂ (n + 1)).continuous_symm
  have hyt : y ∈ (𝓡∂ (n + 1)).symm ⁻¹'
      (chartAt (EuclideanHalfSpace (n + 1)) x).target := hy.1
  rw [Set.inter_comm] at hft
  have key := frontier_inter_open_inter ht (s := Set.range (𝓡∂ (n + 1)))
  have hmem : y ∈ frontier (Set.range (𝓡∂ (n + 1)) ∩
      (𝓡∂ (n + 1)).symm ⁻¹' (chartAt (EuclideanHalfSpace (n + 1)) x).target) ∩
      (𝓡∂ (n + 1)).symm ⁻¹' (chartAt (EuclideanHalfSpace (n + 1)) x).target :=
    ⟨hft, hyt⟩
  rw [key] at hmem
  exact hmem.1

end Problems.Geometry.stokes_bdry_chart
