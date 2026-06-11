-- Direct proof: `faceProj` is the continuous linear map `w ↦ (w ∘ Fin.succ)` transported
-- through `EuclideanSpace.equiv`; smoothness is `contDiff_pi` over coordinate projections
-- composed with the smooth linear equivalence — no sub-goals needed (leaf bypass).
import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs._strategy_s11697

namespace Problems.Geometry.stokes_bdry_manifold

def smooth_face_proj := @Problems.Geometry.stokes_bdry_manifold.s11697

end Problems.Geometry.stokes_bdry_manifold
