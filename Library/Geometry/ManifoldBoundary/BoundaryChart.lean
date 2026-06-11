import Library.Geometry.ManifoldBoundary.BoundaryCoord
import Library.Geometry.ManifoldBoundary.Defs
import Mathlib.Data.Bundle
import Mathlib.Data.Set.Basic
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.InteriorBoundary
import Mathlib.Topology.Basic

/-!
# Boundary Chart for Manifolds with Boundary

This file verifies the four chart axioms for the local chart at a boundary point of an
`n`-dimensional manifold with boundary modelled on `EuclideanHalfSpace (n + 1)`. The chart
sends a neighbourhood of `p : Bdry n M` into the face of the half-space via `faceProj`, with
`faceEmbed` as its inverse; membership in the face is enforced by the coordinate-zero condition
on boundary points.

## Main results

- `chart_map_source` : `chartToFun p` maps `chartSource p` into `chartTarget p`.
- `chart_map_target` : `chartInvFun p` maps `chartTarget p` into `chartSource p`.
- `chart_left_inv` : `chartInvFun p` is a left inverse of `chartToFun p` on `chartSource p`.
- `chart_right_inv` : `chartToFun p (chartInvFun p z) = z` for every `z ∈ chartTarget p`.
- `chart_axioms` : the conjunction of the four chart axioms for every boundary point.
-/

open Bundle
open Library.Geometry.ManifoldBoundary.BoundaryCoord
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBoundary.BoundaryChart

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- `chartToFun p` maps every point of `chartSource p` into `chartTarget p`.
The extended chart image lies in the half-space target, and the zeroth coordinate is zero
because `p` is a boundary point, placing the image in the face slice. -/
theorem chart_map_source (p : Bdry n M) :
    ∀ q ∈ chartSource p, chartToFun p q ∈ chartTarget p := by
  intro q hq
  simp only [chartSource, Set.mem_preimage] at hq
  simp only [chartToFun, chartTarget]
  apply Set.mem_image_of_mem
  constructor
  · exact (extChartAt (𝓡∂ (n + 1)) p.val).map_source hq
  · exact boundary_extChartAt_coord_zero p q hq

/-- `chartInvFun p` maps every point of `chartTarget p` back into `chartSource p`.
Given `z ∈ chartTarget p`, the identity `faceEmbed (faceProj w) = w` (valid since `w 0 = 0`)
shows `faceEmbed z` lies in the extended chart target, and `PartialEquiv.map_target` then
sends it into `chartSource p`. -/
theorem chart_map_target (p : Bdry n M) :
    ∀ z ∈ chartTarget p, chartInvFun p z ∈ chartSource p := by
  intro z hz
  simp only [chartTarget, Set.mem_image] at hz
  obtain ⟨w, ⟨hw_target, hw_zero⟩, hw_proj⟩ := hz
  simp only [Set.mem_setOf_eq] at hw_zero
  have hw_embed : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    have heq : faceEmbed (faceProj w) = w := faceEmbed_faceProj_of_coord_zero w hw_zero
    rw [← hw_proj, heq]
    exact hw_target
  simp only [chartInvFun, dif_pos hw_embed, chartSource, Set.mem_preimage]
  exact (extChartAt (𝓡∂ (n + 1)) p.val).map_target hw_embed

/-- `chartInvFun p` is a left inverse of `chartToFun p` on `chartSource p`.
The boundary condition forces the extended chart image to have zeroth coordinate zero, so
`faceEmbed ∘ faceProj` acts as the identity on that image and the `PartialEquiv.left_inv`
law recovers the original boundary point. -/
theorem chart_left_inv (p : Bdry n M) :
    ∀ q ∈ chartSource p, chartInvFun p (chartToFun p q) = q := by
  intro q hq
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
    faceEmbed_faceProj_of_coord_zero _ hcoord0
  have h_in : faceEmbed (faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val)) ∈
      (extChartAt (𝓡∂ (n + 1)) p.val).target := by rw [hfep]; exact htarget
  simp only [chartInvFun, chartToFun]
  rw [dif_pos h_in]
  apply Subtype.ext
  simp only [hfep]
  exact (extChartAt (𝓡∂ (n + 1)) p.val).left_inv hq

/-- `chartToFun p` applied after `chartInvFun p` is the identity on `chartTarget p`.
For `z ∈ chartTarget p`, the preimage witness `w` satisfies `w 0 = 0`, which gives
`faceEmbed z = w`; `PartialEquiv.right_inv` then reduces the composition to the identity. -/
theorem chart_right_inv (p : Bdry n M) :
    ∀ z ∈ chartTarget p, chartToFun p (chartInvFun p z) = z := by
  intro z hz
  simp only [chartTarget, Set.mem_image] at hz
  obtain ⟨w, ⟨hw_target, hw0⟩, hw_proj⟩ := hz
  simp only [Set.mem_setOf_eq] at hw0
  have hfe : faceEmbed z = w := by
    rw [← hw_proj]; exact faceEmbed_faceProj_of_coord_zero w hw0
  have hfet : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := hfe.symm ▸ hw_target
  have hinvfun : chartInvFun p z =
      ⟨(extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z),
        faceEmbed_symm_mem_boundary p z hfet⟩ := by
    simp only [chartInvFun, dif_pos hfet]
  rw [hinvfun]
  simp only [chartToFun, faceProj]
  rw [(extChartAt (𝓡∂ (n + 1)) p.val).right_inv hfet]
  conv_lhs => rw [hfe]
  exact hw_proj

/-- The four chart axioms hold simultaneously for every boundary point `p`:
source maps to target, target maps to source, and both inverse laws hold. -/
theorem chart_axioms (p : Bdry n M) :
    (∀ q ∈ chartSource p, chartToFun p q ∈ chartTarget p) ∧
    (∀ z ∈ chartTarget p, chartInvFun p z ∈ chartSource p) ∧
    (∀ q ∈ chartSource p, chartInvFun p (chartToFun p q) = q) ∧
    (∀ z ∈ chartTarget p, chartToFun p (chartInvFun p z) = z) :=
  ⟨chart_map_source p, chart_map_target p, chart_left_inv p, chart_right_inv p⟩

end Library.Geometry.ManifoldBoundary.BoundaryChart
