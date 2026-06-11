import Library.Geometry.ManifoldBoundary.Defs
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.ENat.Basic
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.IsManifold.InteriorBoundary
import Mathlib.Topology.Constructions
import Mathlib.Topology.Defs.Basic

/-!
# Boundary coordinate lemmas for manifolds with boundary

This file establishes that boundary points of a manifold with corners have vanishing
zeroth coordinate in any extended chart. The main results chain together: a boundary
point maps into the frontier of its extended chart's target, that frontier lies inside
the frontier of the half-space model's range, and membership there forces the zeroth
coordinate to zero.

## Main statements

- `faceEmbed_faceProj_of_coord_zero`: round-tripping through `faceProj` then `faceEmbed`
  is the identity when the zeroth coordinate vanishes.
- `boundary_mem_frontier_target`: boundary points map to the frontier of the extended
  chart's target.
- `coord_zero_of_frontier_range`: points in the frontier of the half-space model's range
  have vanishing zeroth coordinate.
- `frontier_range_of_frontier_target`: points in the frontier of an extended chart's target
  lie in the frontier of the model's range.
- `boundary_extChartAt_coord_zero`: the extended chart value at a boundary point has
  vanishing zeroth coordinate.
-/

open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBoundary.BoundaryCoord

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- Round-tripping a vector through `faceProj` then `faceEmbed` recovers the original
vector provided its zeroth coordinate is zero. -/
theorem faceEmbed_faceProj_of_coord_zero (w : EuclideanSpace ℝ (Fin (n + 1)))
    (h0 : w 0 = 0) : faceEmbed (faceProj w) = w := by
  ext j
  simp only [Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed, faceProj,
    EuclideanSpace.basisFun_apply]
  refine Fin.cases ?_ ?_ j
  · simp [(Fin.succ_ne_zero _).symm, h0]
  · intro i
    simp [Pi.single_apply, Fin.succ_inj]

/-- A boundary point maps to the frontier of the target of the extended chart at any
base point whose source contains it. -/
theorem boundary_mem_frontier_target (x q : M)
    (hq : q ∈ (extChartAt (𝓡∂ (n + 1)) x).source)
    (hbd : q ∈ (𝓡∂ (n + 1)).boundary M) :
    extChartAt (𝓡∂ (n + 1)) x q ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target := by
  have hqs : q ∈ (chartAt (EuclideanHalfSpace (n + 1)) x).source := by
    rwa [← extChartAt_source (𝓡∂ (n + 1)) x]
  have hbd' : (𝓡∂ (n + 1)).IsBoundaryPoint q := hbd
  rw [ModelWithCorners.isBoundaryPoint_iff_of_mem_atlas
      (hn := (by exact_mod_cast ENat.top_ne_zero : (∞ : WithTop ℕ∞) ≠ 0))
      (he := chart_mem_atlas _ x)
      (hx := hqs)] at hbd'
  have : (chartAt (EuclideanHalfSpace (n + 1)) x).extend (𝓡∂ (n + 1)) =
      extChartAt (𝓡∂ (n + 1)) x := rfl
  rw [this] at hbd'
  exact hbd'

/-- A point in the frontier of the range of the half-space model `𝓡∂ (n + 1)` has
vanishing zeroth coordinate. -/
theorem coord_zero_of_frontier_range (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hfr : y ∈ frontier (Set.range (𝓡∂ (n + 1)))) :
    y 0 = 0 := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  rw [frontier_range_modelWithCornersEuclideanHalfSpace] at hfr
  exact hfr.symm

/-- A point in the frontier of an extended chart's target that also lies in the target
belongs to the frontier of the half-space model's range. -/
theorem frontier_range_of_frontier_target (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
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

/-- For boundary points `p` and `q` of `M`, if `q` lies in the source of the extended
chart at `p`, then the zeroth coordinate of the chart value vanishes. -/
theorem boundary_extChartAt_coord_zero (p q : Bdry n M)
    (hq : q.val ∈ (extChartAt (𝓡∂ (n + 1)) p.val).source) :
    extChartAt (𝓡∂ (n + 1)) p.val q.val 0 = 0 := by
  have hmem : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      (extChartAt (𝓡∂ (n + 1)) p.val).target :=
    (extChartAt (𝓡∂ (n + 1)) p.val).map_source hq
  have hft : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      frontier (extChartAt (𝓡∂ (n + 1)) p.val).target :=
    boundary_mem_frontier_target p.val q.val hq q.2
  have hfr : extChartAt (𝓡∂ (n + 1)) p.val q.val ∈
      frontier (Set.range (𝓡∂ (n + 1))) :=
    frontier_range_of_frontier_target p.val _ hmem hft
  exact coord_zero_of_frontier_range _ hfr

end Library.Geometry.ManifoldBoundary.BoundaryCoord
