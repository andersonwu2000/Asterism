import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs.L_smooth_face_proj
import Problems.Geometry.stokes_bdry_manifold.proofs.L_smooth_face_embed

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBdry.ChartedBdry

namespace Problems.Geometry.stokes_bdry_manifold

open scoped Manifold ContDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier

-- contdiffon_face_sandwich: ContDiffOn of faceProj ∘ extChart-coord-change ∘ faceEmbed
-- by composing smooth_face_proj, contDiffOn_ext_coord_change, and smooth_face_embed
set_option maxHeartbeats 400000 in
-- contDiffOn_ext_coord_change elaboration on EuclideanHalfSpace model needs extra budget
theorem contdiffon_face_sandwich {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]
    (p q : Bdry n M) (s : Set (EuclideanSpace ℝ (Fin n)))
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
    smooth_face_proj.contDiffOn.comp hmid (Set.mapsTo_univ _ _)
  exact houter.comp smooth_face_embed.contDiffOn hmaps

end Problems.Geometry.stokes_bdry_manifold

