-- Reduce IsManifold to per-pair transition smoothness via isManifold_of_contDiffOn; the
-- self-model 𝓘(ℝ, E) is the identity, so the obligation simp-collapses to plain ContDiffOn
-- on the transition source. Atlas = Set.range bdryChart, so pairs destruct to bdryChart p/q.
-- Three sub-goals: (A) the transition agrees pointwise with the sandwich
-- faceProj ∘ (extChartAt q ∘ (extChartAt p).symm) ∘ faceEmbed; (B) faceEmbed maps the
-- transition source into the extChart coord-change source; (C) the sandwich is ContDiffOn
-- on any set with property (B) — outer/inner via landed smooth_face_proj/smooth_face_embed,
-- middle via contDiffOn_ext_coord_change. Combine: C(B) then ContDiffOn.congr with A.
import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs._strategy_s11699

namespace Problems.Geometry.stokes_bdry_manifold

@[instance]
def main := @Problems.Geometry.stokes_bdry_manifold.s11699

end Problems.Geometry.stokes_bdry_manifold
