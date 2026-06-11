import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs.L_bdry_transition_eq_face_sandwich
import Problems.Geometry.stokes_bdry_manifold.proofs.L_contdiffon_face_sandwich
import Problems.Geometry.stokes_bdry_manifold.proofs.L_face_embed_mapsto_ext_trans_source

open scoped Manifold Bundle ContDiff
open Bundle

namespace Problems.Geometry.stokes_bdry_manifold

open scoped Manifold ContDiff
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs

open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBdry.ChartedBdry

-- Reduce IsManifold to per-pair transition smoothness via isManifold_of_contDiffOn; the
-- self-model 𝓘(ℝ, E) is the identity, so the obligation simp-collapses to plain ContDiffOn
-- on the transition source. Atlas = Set.range bdryChart, so pairs destruct to bdryChart p/q.
-- Three sub-goals: (A) the transition agrees pointwise with the sandwich
-- faceProj ∘ (extChartAt q ∘ (extChartAt p).symm) ∘ faceEmbed; (B) faceEmbed maps the
-- transition source into the extChart coord-change source; (C) the sandwich is ContDiffOn
-- on any set with property (B) — outer/inner via landed smooth_face_proj/smooth_face_embed,
-- middle via contDiffOn_ext_coord_change. Combine: C(B) then ContDiffOn.congr with A.
theorem s11699 : ∀ {n : ℕ} {M : Type*} [TopologicalSpace M]
    [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M],
    IsManifold (𝓘(ℝ, EuclideanSpace ℝ (Fin n))) ∞ (Bdry n M)  := by
  intro n M _ _ _
  apply isManifold_of_contDiffOn
  rintro e e' ⟨p, rfl⟩ ⟨q, rfl⟩
  have h_eq := bdry_transition_eq_face_sandwich p q
  have h_maps := face_embed_mapsto_ext_trans_source p q
  have h_smooth := contdiffon_face_sandwich p q _ h_maps
  simp only [modelWithCornersSelf_coe, modelWithCornersSelf_coe_symm, Set.preimage_id,
    Set.range_id, Set.inter_univ, Function.comp_id, Function.id_comp]
  exact h_smooth.congr h_eq


end Problems.Geometry.stokes_bdry_manifold

