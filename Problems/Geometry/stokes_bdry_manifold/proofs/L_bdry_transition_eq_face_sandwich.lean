-- Direct proof: the transition is definitionally `chartToFun q ∘ chartInvFun p`; on the
-- transition source `z ∈ chartTarget p`, so the Library lemma
-- `chartInvFun_val_eq_extChartAt_symm_faceEmbed` rewrites the inner point to
-- `(extChartAt p.val).symm (faceEmbed z)`, after which both sides agree by `rfl`.
import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs._strategy_s11701

namespace Problems.Geometry.stokes_bdry_manifold

def bdry_transition_eq_face_sandwich := @Problems.Geometry.stokes_bdry_manifold.s11701

end Problems.Geometry.stokes_bdry_manifold
