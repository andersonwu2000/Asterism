-- Direct proof: destruct membership in the transition source into its two defeq components
-- (z ∈ chartTarget p, and chartInvFun p z landing in chartSource q), then translate each via
-- the Library bricks chartTarget_eq_faceEmbed_preimage (target membership of faceEmbed z)
-- and chartInvFun_val_eq_extChartAt_symm_faceEmbed (identifying the inverse chart value with
-- (extChartAt p.val).symm (faceEmbed z)) to land in the extChart coord-change source.
import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs._strategy_s11700

namespace Problems.Geometry.stokes_bdry_manifold

def face_embed_mapsto_ext_trans_source := @Problems.Geometry.stokes_bdry_manifold.s11700

end Problems.Geometry.stokes_bdry_manifold
