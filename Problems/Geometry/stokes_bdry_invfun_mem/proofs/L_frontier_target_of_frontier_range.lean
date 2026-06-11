import Mathlib
import Problems.Geometry.stokes_bdry_invfun_mem.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry

namespace Problems.Geometry.stokes_bdry_invfun_mem

open scoped Manifold ContDiff

-- frontier_target_of_frontier_range: a point in frontier(range I) that lies in the extChartAt
-- target stays in the frontier of that target, via frontier_inter_open_inter + extChartAt_target.
theorem frontier_target_of_frontier_range {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target)
    (hfr : y ∈ frontier (Set.range (𝓡∂ (n + 1)))) :
    y ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target := by
  rw [extChartAt_target] at hy ⊢
  have ht : IsOpen ((𝓡∂ (n + 1)).symm ⁻¹'
      (chartAt (EuclideanHalfSpace (n + 1)) x).target) :=
    (chartAt _ x).open_target.preimage (𝓡∂ (n + 1)).continuous_symm
  have hyt : y ∈ (𝓡∂ (n + 1)).symm ⁻¹' (chartAt (EuclideanHalfSpace (n + 1)) x).target :=
    hy.1
  rw [Set.inter_comm]
  have key := frontier_inter_open_inter ht (s := Set.range (𝓡∂ (n + 1)))
  have hmem : y ∈ frontier (Set.range (𝓡∂ (n + 1))) ∩
      (𝓡∂ (n + 1)).symm ⁻¹' (chartAt (EuclideanHalfSpace (n + 1)) x).target :=
    ⟨hfr, hyt⟩
  rw [← key] at hmem
  exact hmem.1

end Problems.Geometry.stokes_bdry_invfun_mem
