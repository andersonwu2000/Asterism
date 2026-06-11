import Library.Geometry.ManifoldBoundary.CompactBdry
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.IsManifold.InteriorBoundary
import Mathlib.Topology.Constructions

/-!
# Half-space frontier and manifold boundary

This file characterises when points obtained by embedding a face into the Euclidean half-space
model land in the manifold boundary.  The embedding `faceEmbed` maps an `n`-dimensional vector
into the `(n+1)`-dimensional half-space along the `succ`-indexed coordinates; its image sits in
`frontier (Set.range (𝓡∂ (n+1)))` because the zeroth coordinate vanishes.  Combined with a chart
transfer lemma, this shows that `extChartAt.symm (faceEmbed z)` belongs to the manifold boundary.

## Main definitions

- `faceEmbed`: embeds an `n`-dimensional vector into the `(n+1)`-dimensional Euclidean half-space
  along the `Fin.succ`-indexed basis vectors.

## Main statements

- `faceEmbed_mem_frontier_range`: `faceEmbed z` lies in the frontier of the half-space model range.
- `frontier_target_of_frontier_range`: a frontier point of `range (𝓡∂ (n+1))` inside an extended
  chart target also lies in the frontier of that target.
- `boundary_of_mem_frontier_target`: a point in the frontier of an extended chart target is sent
  to the manifold boundary by `extChartAt.symm`.
- `symm_mem_boundary_of_frontier`: combines the two preceding lemmas.
- `faceEmbed_symm_mem_boundary`: `extChartAt.symm (faceEmbed z)` lies in the manifold boundary.
-/

open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- Embed an `n`-dimensional vector into the `(n+1)`-dimensional Euclidean half-space by
placing its coordinates along the `Fin.succ`-indexed basis vectors. -/
noncomputable def faceEmbed (z : EuclideanSpace ℝ (Fin n)) :
    EuclideanSpace ℝ (Fin (n + 1)) :=
  ∑ i : Fin n, z i • EuclideanSpace.basisFun (Fin (n + 1)) ℝ i.succ

/-- `faceEmbed z` lies in the frontier of the half-space model's range because its zeroth
coordinate is zero. -/
theorem faceEmbed_mem_frontier_range (z : EuclideanSpace ℝ (Fin n)) :
    faceEmbed z ∈ frontier (Set.range (𝓡∂ (n + 1))) := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  rw [frontier_range_modelWithCornersEuclideanHalfSpace]
  simp only [Set.mem_setOf_eq]
  simp [faceEmbed, EuclideanSpace.basisFun_apply, Fin.succ_ne_zero]

/-- A point in `frontier (Set.range (𝓡∂ (n+1)))` that lies in the target of an extended chart
also lies in the frontier of that target. -/
theorem frontier_target_of_frontier_range (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
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

/-- If `y` lies in the frontier of an extended chart's target, then `extChartAt.symm y` is a
manifold boundary point. -/
theorem boundary_of_mem_frontier_target (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target)
    (hft : y ∈ frontier (extChartAt (𝓡∂ (n + 1)) x).target) :
    (extChartAt (𝓡∂ (n + 1)) x).symm y ∈ (𝓡∂ (n + 1)).boundary M := by
  rw [ModelWithCorners.boundary, Set.mem_setOf_eq]
  have hx_src : (extChartAt (𝓡∂ (n + 1)) x).symm y ∈
      (chartAt (EuclideanHalfSpace (n + 1)) x).source := by
    rw [← extChartAt_source (𝓡∂ (n + 1)) x]
    exact (extChartAt (𝓡∂ (n + 1)) x).map_target hy
  rw [ModelWithCorners.isBoundaryPoint_iff_of_mem_atlas
      (hn := (by exact_mod_cast ENat.top_ne_zero : (∞ : WithTop ℕ∞) ≠ 0))
      (he := chart_mem_atlas _ x)
      (hx := hx_src)]
  have : (chartAt (EuclideanHalfSpace (n + 1)) x).extend (𝓡∂ (n + 1)) =
      extChartAt (𝓡∂ (n + 1)) x := rfl
  rw [this, (extChartAt (𝓡∂ (n + 1)) x).right_inv hy]
  exact hft

/-- If `y` lies in `frontier (Set.range (𝓡∂ (n+1)))` and in the target of `extChartAt x`, then
`extChartAt.symm y` is a manifold boundary point. -/
theorem symm_mem_boundary_of_frontier (x : M) (y : EuclideanSpace ℝ (Fin (n + 1)))
    (hy : y ∈ (extChartAt (𝓡∂ (n + 1)) x).target)
    (hfr : y ∈ frontier (Set.range (𝓡∂ (n + 1)))) :
    (extChartAt (𝓡∂ (n + 1)) x).symm y ∈ (𝓡∂ (n + 1)).boundary M := by
  exact boundary_of_mem_frontier_target x y hy (frontier_target_of_frontier_range x y hy hfr)

/-- If `faceEmbed z` lies in the target of the extended chart at a boundary point `p`, then
`extChartAt.symm (faceEmbed z)` belongs to the manifold boundary. -/
theorem faceEmbed_symm_mem_boundary (p : Bdry n M) (z : EuclideanSpace ℝ (Fin n))
    (hy : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target) :
    (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) ∈ (𝓡∂ (n + 1)).boundary M := by
  exact symm_mem_boundary_of_frontier p.val (faceEmbed z) hy (faceEmbed_mem_frontier_range z)

end Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
