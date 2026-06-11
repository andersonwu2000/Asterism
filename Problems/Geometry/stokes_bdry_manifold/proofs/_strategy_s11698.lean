import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs

namespace Problems.Geometry.stokes_bdry_manifold

open scoped Manifold ContDiff

-- Direct proof: faceEmbed is the finite sum ∑ i, z i • basisFun i.succ, smooth termwise.
-- Each term is (coordinate projection, a continuous linear map, hence ContDiff) • constant;
-- ContDiff.sum closes the goal. (`open scoped ContDiff` is required for the ∞ exponent.)
theorem s11698 :
    ContDiff ℝ ∞
      (Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed (n := n) :
        EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n + 1)))  := by
  unfold Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed
  apply ContDiff.sum
  intro i _
  exact ((EuclideanSpace.proj i : EuclideanSpace ℝ (Fin n) →L[ℝ] ℝ).contDiff).smul contDiff_const

end Problems.Geometry.stokes_bdry_manifold
