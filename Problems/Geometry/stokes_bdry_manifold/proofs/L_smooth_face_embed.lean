-- Direct proof: faceEmbed is the finite sum ∑ i, z i • basisFun i.succ, smooth termwise.
-- Each term is (coordinate projection, a continuous linear map, hence ContDiff) • constant;
-- ContDiff.sum closes the goal. (`open scoped ContDiff` is required for the ∞ exponent.)
import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs
import Problems.Geometry.stokes_bdry_manifold.proofs._strategy_s11698

namespace Problems.Geometry.stokes_bdry_manifold

def smooth_face_embed := @Problems.Geometry.stokes_bdry_manifold.s11698

end Problems.Geometry.stokes_bdry_manifold
