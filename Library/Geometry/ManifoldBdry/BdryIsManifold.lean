import Library.Geometry.ManifoldBdry.ChartedBdry -- P8: bdryChart + mem_bdryChart_source
import Library.Geometry.ManifoldBdry.SmoothFaceMaps
import Library.Geometry.ManifoldBoundary.Defs   -- chart data, Bdry, TopologicalSpace (Bdry n M)
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.ContDiff.Comp
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Set.Function
import Mathlib.Geometry.Manifold.ChartedSpace
import Mathlib.Geometry.Manifold.Instances.Real
import Mathlib.Geometry.Manifold.IsManifold.Basic
import Mathlib.Geometry.Manifold.IsManifold.ExtChartAt

/-!
# The boundary of a manifold-with-boundary is a smooth manifold

Given an `n+1`-dimensional manifold-with-boundary `M`, its boundary `∂M` carries a natural
smooth manifold structure modelled on `EuclideanSpace ℝ (Fin n)`. The atlas is the range of
`bdryChart`, and transition maps are given by the face-sandwich `faceProj ∘ φ ∘ faceEmbed`,
where `φ` is the coordinate change of the ambient manifold.

## Main definitions

- `instBdryChartedSpace`: `∂M` is a charted space over `EuclideanSpace ℝ (Fin n)`.

## Main statements

- `bdry_transition_eq_face_sandwich`: transition maps factor through the ambient coord change.
- `face_embed_mapsto_ext_trans_source`: `faceEmbed` maps boundary transition sources into
  the ambient coordinate-change source.
- `contDiffOn_face_sandwich`: the face-sandwich composition is smooth.
- `isManifold_bdry`: `∂M` is a smooth manifold.
-/

open Bundle
open Library.Geometry.ManifoldBdry.BdryChart
open Library.Geometry.ManifoldBdry.ChartedBdry
open Library.Geometry.ManifoldBdry.SmoothFaceMaps
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.BdryIsManifold

variable {n : ℕ} {M : Type*} [TopologicalSpace M]
  [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]

/-- `∂M` is a charted space over `EuclideanSpace ℝ (Fin n)`: the atlas is the range of
`bdryChart`, each point charted by `bdryChart p`. -/
noncomputable instance instBdryChartedSpace :
    ChartedSpace (EuclideanSpace ℝ (Fin n)) (Bdry n M) where
  atlas := Set.range bdryChart
  chartAt p := bdryChart p
  mem_chart_source p := mem_bdryChart_source p
  chart_mem_atlas p := ⟨p, rfl⟩

/-- The transition map between two boundary charts equals `faceProj ∘ φ ∘ faceEmbed`, where
`φ` is the ambient coordinate change between `p.val` and `q.val`. -/
theorem bdry_transition_eq_face_sandwich (p q : Bdry n M)
    (z : EuclideanSpace ℝ (Fin n))
    (hz : z ∈ ((bdryChart p).symm ≫ₕ bdryChart q).source) :
    ((bdryChart p).symm ≫ₕ bdryChart q) z =
      faceProj ((extChartAt (𝓡∂ (n + 1)) q.val ∘
        (extChartAt (𝓡∂ (n + 1)) p.val).symm) (faceEmbed z)) := by
  have hz_tgt : z ∈ chartTarget p := hz.1
  have hval := chartInvFun_val_eq_extChartAt_symm_faceEmbed p z hz_tgt
  change chartToFun q (chartInvFun p z) = _
  unfold chartToFun
  rw [hval]
  rfl

/-- `faceEmbed` maps the source of the boundary transition `(bdryChart p).symm ≫ₕ bdryChart q`
into the source of the ambient coordinate change
`(extChartAt p.val).symm ≫ extChartAt q.val`. -/
theorem face_embed_mapsto_ext_trans_source (p q : Bdry n M) :
    Set.MapsTo faceEmbed ((bdryChart p).symm ≫ₕ bdryChart q).source
      ((extChartAt (𝓡∂ (n + 1)) p.val).symm ≫ extChartAt (𝓡∂ (n + 1)) q.val).source := by
  intro z hz
  have hzp : z ∈ chartTarget p := hz.1
  have hzq : (chartInvFun p z).val ∈ (extChartAt (𝓡∂ (n + 1)) q.val).source := hz.2
  have hT : faceEmbed z ∈ (extChartAt (𝓡∂ (n + 1)) p.val).target := by
    rw [chartTarget_eq_faceEmbed_preimage p] at hzp; exact hzp
  refine ⟨hT, ?_⟩
  simp only [PartialEquiv.symm_symm, Set.mem_preimage]
  rw [← chartInvFun_val_eq_extChartAt_symm_faceEmbed p z hzp]
  exact hzq

set_option maxHeartbeats 400000 in
-- contDiffOn_ext_coord_change elaboration on EuclideanHalfSpace model needs extra budget
/-- The face-sandwich `z ↦ faceProj (φ (faceEmbed z))` is smooth on any set `s` whose
`faceEmbed`-image lies in the source of the ambient coordinate change `φ`. -/
theorem contDiffOn_face_sandwich (p q : Bdry n M) (s : Set (EuclideanSpace ℝ (Fin n)))
    (hmaps : Set.MapsTo faceEmbed s
      ((extChartAt (𝓡∂ (n + 1)) p.val).symm ≫ extChartAt (𝓡∂ (n + 1)) q.val).source) :
    ContDiffOn ℝ ∞
      (fun z => faceProj ((extChartAt (𝓡∂ (n + 1)) q.val ∘
        (extChartAt (𝓡∂ (n + 1)) p.val).symm) (faceEmbed z))) s := by
  have hmid : ContDiffOn ℝ ∞
      (extChartAt (𝓡∂ (n + 1)) q.val ∘ (extChartAt (𝓡∂ (n + 1)) p.val).symm)
      ((extChartAt (𝓡∂ (n + 1)) p.val).symm ≫ extChartAt (𝓡∂ (n + 1)) q.val).source :=
    contDiffOn_ext_coord_change q.val p.val
  have houter : ContDiffOn ℝ ∞
      (faceProj ∘ (extChartAt (𝓡∂ (n + 1)) q.val ∘ (extChartAt (𝓡∂ (n + 1)) p.val).symm))
      ((extChartAt (𝓡∂ (n + 1)) p.val).symm ≫ extChartAt (𝓡∂ (n + 1)) q.val).source :=
    contDiff_faceProj.contDiffOn.comp hmid (Set.mapsTo_univ _ _)
  exact houter.comp contDiff_faceEmbed.contDiffOn hmaps

/-- `∂M` is a smooth manifold modelled on `EuclideanSpace ℝ (Fin n)`. -/
@[instance]
theorem isManifold_bdry : IsManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) ∞ (Bdry n M) := by
  apply isManifold_of_contDiffOn
  rintro e e' ⟨p, rfl⟩ ⟨q, rfl⟩
  have h_eq := bdry_transition_eq_face_sandwich p q
  have h_maps := face_embed_mapsto_ext_trans_source p q
  have h_smooth := contDiffOn_face_sandwich p q _ h_maps
  simp only [modelWithCornersSelf_coe, modelWithCornersSelf_coe_symm, Set.preimage_id,
    Set.range_id, Set.inter_univ, Function.comp_id, Function.id_comp]
  exact h_smooth.congr h_eq

end Library.Geometry.ManifoldBdry.BdryIsManifold
