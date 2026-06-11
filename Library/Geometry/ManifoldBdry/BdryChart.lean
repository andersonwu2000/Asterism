import Library.Geometry.ManifoldBdry.FaceMap
import Library.Geometry.ManifoldBoundary.BoundaryCoord
import Library.Geometry.ManifoldBoundary.Defs
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Bundle
import Mathlib.Data.Set.Basic
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt
import Mathlib.Geometry.Manifold.IsManifold.InteriorBoundary
import Mathlib.Geometry.Manifold.Notation
import Mathlib.Topology.Basic
import Mathlib.Topology.Defs.Induced

/-!
# Boundary chart topology for manifolds with boundary

This file establishes the topological properties of the boundary chart construction for a
smooth manifold with boundary `M` modelled on `EuclideanHalfSpace (n + 1)`. It shows that
the chart source and target are open sets and that the forward and inverse chart maps are
continuous on their respective domains.

## Main statements

- `chartTarget_eq_faceEmbed_preimage`: the chart target equals the preimage of the extended
  chart's target under `faceEmbed`.
- `isOpen_chartSource`: the chart source `chartSource p` is open.
- `isOpen_chartTarget`: the chart target `chartTarget p` is open.
- `continuousOn_chartToFun`: the chart map `chartToFun p` is continuous on `chartSource p`.
- `continuousOn_chartInvFun`: the inverse chart map `chartInvFun p` is continuous on
  `chartTarget p`.
- `bdryChart_isOpen_continuousOn`: collects all four topological properties.
-/

open Bundle
open Library.Geometry.ManifoldBdry.FaceMap
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.BdryChart

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- The chart target equals the preimage of the extended chart's target under `faceEmbed`.
A point `z` lies in `chartTarget p` iff `faceEmbed z` lies in
`(extChartAt (𝓡∂ (n + 1)) p.val).target`. -/
theorem chartTarget_eq_faceEmbed_preimage (p : Bdry n M) :
    chartTarget p = faceEmbed ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).target := by
  ext z
  simp only [chartTarget, Set.mem_image, Set.mem_inter_iff, Set.mem_setOf_eq, Set.mem_preimage]
  constructor
  · rintro ⟨w, ⟨hwT, hw0⟩, rfl⟩
    rwa [Library.Geometry.ManifoldBoundary.BoundaryCoord.faceEmbed_faceProj_of_coord_zero w hw0]
  · intro hz
    exact ⟨faceEmbed z, ⟨hz,
      Library.Geometry.ManifoldBoundary.BoundaryCoord.coord_zero_of_frontier_range _
        (faceEmbed_mem_frontier_range z)⟩, faceProj_faceEmbed z⟩

/-- The chart source `chartSource p` is open as a subtype preimage of the open extended
chart source. -/
theorem isOpen_chartSource (p : Bdry n M) : IsOpen (chartSource p) := by
  unfold chartSource
  exact (isOpen_extChartAt_source p.val).preimage continuous_subtype_val

/-- The chart target `chartTarget p` is open, obtained via the `faceEmbed`-preimage
description and openness of the extended chart target. -/
theorem isOpen_chartTarget (p : Bdry n M) : IsOpen (chartTarget p) := by
  haveI : NeZero (n + 1) := ⟨Nat.succ_ne_zero n⟩
  rw [chartTarget_eq_faceEmbed_preimage p, extChartAt_target]
  rw [Set.preimage_inter]
  have h_range_univ : faceEmbed ⁻¹' Set.range (𝓡∂ (n + 1)) = Set.univ := by
    ext z
    simp only [Set.mem_preimage, Set.mem_univ, iff_true,
      range_modelWithCornersEuclideanHalfSpace, Set.mem_setOf_eq]
    have := Library.Geometry.ManifoldBoundary.BoundaryCoord.coord_zero_of_frontier_range
      (faceEmbed z) (faceEmbed_mem_frontier_range z)
    linarith
  rw [h_range_univ, Set.inter_univ]
  exact ((chartAt (EuclideanHalfSpace (n + 1)) p.val).open_target.preimage
    (𝓡∂ (n + 1)).continuous_symm).preimage continuous_face_embed

/-- The forward chart map `chartToFun p` is continuous on `chartSource p`, obtained by
composing `faceProj` with the extended chart. -/
theorem continuousOn_chartToFun (p : Bdry n M) :
    ContinuousOn (chartToFun p) (chartSource p) := by
  change ContinuousOn (fun q : Bdry n M ↦ faceProj (extChartAt (𝓡∂ (n + 1)) p.val q.val))
      (Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).source)
  apply Continuous.comp_continuousOn continuous_face_proj
  apply ContinuousOn.comp (continuousOn_extChartAt (I := 𝓡∂ (n + 1)) p.val)
    (continuous_subtype_val.continuousOn
      (s := Subtype.val ⁻¹' (extChartAt (𝓡∂ (n + 1)) p.val).source))
  intro _ hq; exact hq

/-- On `chartTarget p`, the underlying value of `chartInvFun p z` equals
`(extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z)`. -/
theorem chartInvFun_val_eq_extChartAt_symm_faceEmbed (p : Bdry n M) :
    ∀ z ∈ chartTarget p,
      (chartInvFun p z).val = (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) := by
  intro z hz
  have hmem : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    have h := chartTarget_eq_faceEmbed_preimage p
    rw [h] at hz; exact hz
  simp only [chartInvFun, dif_pos hmem]

/-- The composition `(extChartAt (𝓡∂ (n + 1)) p.val).symm ∘ faceEmbed` is continuous on
`chartTarget p`. -/
theorem continuousOn_extChartAt_symm_faceEmbed (p : Bdry n M) : ContinuousOn
    (fun z : EuclideanSpace ℝ (Fin n) ↦ (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z))
    (chartTarget p) := by
  have hmaps :
      Set.MapsTo faceEmbed (chartTarget p) (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    intro z hz
    rw [chartTarget_eq_faceEmbed_preimage p] at hz
    exact hz
  exact (continuousOn_extChartAt_symm p.val).comp
    continuous_face_embed.continuousOn hmaps

/-- The inverse chart map `chartInvFun p` is continuous on `chartTarget p`. -/
theorem continuousOn_chartInvFun (p : Bdry n M) :
    ContinuousOn (chartInvFun p) (chartTarget p) := by
  have h_val_eq : ∀ z ∈ chartTarget p,
      (chartInvFun p z).val = (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z) :=
    chartInvFun_val_eq_extChartAt_symm_faceEmbed p
  have h_cont_symm : ContinuousOn
      (fun z : EuclideanSpace ℝ (Fin n) ↦
        (extChartAt (𝓡∂ (n + 1)) p.val).symm (faceEmbed z))
      (chartTarget p) :=
    continuousOn_extChartAt_symm_faceEmbed p
  have h_ind : Topology.IsInducing (Subtype.val : Bdry n M → M) :=
    Topology.IsInducing.subtypeVal
  exact h_ind.continuousOn_iff.mpr (h_cont_symm.congr fun z hz ↦ h_val_eq z hz)

/-- The boundary chart at `p` has open source and target, and both the forward and inverse
maps are continuous on their respective domains. -/
theorem bdryChart_isOpen_continuousOn (p : Bdry n M) :
    IsOpen (chartSource p) ∧ IsOpen (chartTarget p) ∧
    ContinuousOn (chartToFun p) (chartSource p) ∧
    ContinuousOn (chartInvFun p) (chartTarget p) :=
  ⟨isOpen_chartSource p, isOpen_chartTarget p,
    continuousOn_chartToFun p, continuousOn_chartInvFun p⟩

end Library.Geometry.ManifoldBdry.BdryChart
