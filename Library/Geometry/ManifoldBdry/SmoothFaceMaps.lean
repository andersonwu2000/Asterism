import Library.Geometry.ManifoldBdry.ChartedBdry -- P8: bdryChart + mem_bdryChart_source
import Library.Geometry.ManifoldBoundary.Defs   -- chart data, Bdry, TopologicalSpace (Bdry n M)
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.ContDiff.Comp
import Mathlib.Analysis.Calculus.ContDiff.Operations
import Mathlib.Analysis.InnerProductSpace.PiL2

/-!
# Smooth Face Maps for Manifold Boundary

This file proves that the face projection and face embedding maps associated with the
Euclidean half-space frontier are smooth of class `C^∞`.

## Main statements

- `contDiff_faceProj`: the face projection `faceProj` is `C^∞`.
- `contDiff_faceEmbed`: the face embedding `faceEmbed` is `C^∞`.
-/

open Library.Geometry.ManifoldBoundary.Defs
open scoped Manifold ContDiff

namespace Library.Geometry.ManifoldBdry.SmoothFaceMaps

variable {n : ℕ}

/-- The face projection `faceProj : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin n)`
is smooth of class `C^∞`. -/
theorem contDiff_faceProj :
    ContDiff ℝ ∞ (faceProj (n := n)) := by
  have h : ContDiff ℝ ∞
      (fun w : EuclideanSpace ℝ (Fin (n + 1)) ↦ fun i : Fin n ↦ w i.succ) :=
    contDiff_pi.2 fun i ↦ (EuclideanSpace.proj (i.succ : Fin (n + 1)) (𝕜 := ℝ)).contDiff
  exact ((EuclideanSpace.equiv (Fin n) ℝ).symm.contDiff).comp h

/-- The face embedding `faceEmbed : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n + 1))`
is smooth of class `C^∞`. -/
theorem contDiff_faceEmbed :
    ContDiff ℝ ∞
      (Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed (n := n) :
        EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n + 1))) := by
  unfold Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed
  apply ContDiff.sum
  intro i _
  exact ((EuclideanSpace.proj i : EuclideanSpace ℝ (Fin n) →L[ℝ] ℝ).contDiff).smul contDiff_const

end Library.Geometry.ManifoldBdry.SmoothFaceMaps
