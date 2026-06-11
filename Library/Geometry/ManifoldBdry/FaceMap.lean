import Library.Geometry.ManifoldBoundary.Defs
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Topology.Algebra.Monoid
import Mathlib.Topology.Algebra.MulAction
import Mathlib.Topology.Constructions

/-!
# Face Maps for Manifold Boundary Charts

This file establishes continuity properties of the face projection and face embedding maps
between Euclidean spaces, arising in the chart structure of manifolds with boundary.

## Main statements

- `continuous_face_proj`: The face projection `faceProj : ℝⁿ⁺¹ → ℝⁿ` is continuous.
- `faceProj_faceEmbed`: Projecting after embedding recovers the original vector.
- `continuous_face_embed`: The face embedding `faceEmbed : ℝⁿ → ℝⁿ⁺¹` is continuous.
-/

open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.Defs
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.ManifoldBdry.FaceMap

variable {n : ℕ}

/-- The face projection `faceProj : ℝⁿ⁺¹ → ℝⁿ`, which reads off the `i.succ` coordinates,
is continuous. -/
theorem continuous_face_proj :
    Continuous (faceProj : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin n)) := by
  have h : Continuous (fun w : EuclideanSpace ℝ (Fin (n + 1)) ↦ fun i : Fin n ↦ w i.succ) :=
    continuous_pi fun i => (EuclideanSpace.proj (i.succ : Fin (n + 1))).continuous
  exact (EuclideanSpace.equiv (Fin n) ℝ).symm.continuous.comp h

/-- The face projection is a left inverse of the face embedding: projecting after embedding
recovers the original vector. -/
theorem faceProj_faceEmbed (z : EuclideanSpace ℝ (Fin n)) :
    faceProj (faceEmbed z) = z := by
  ext i
  simp only [Library.Geometry.ManifoldBoundary.Defs.faceProj,
    Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed,
    EuclideanSpace.basisFun_apply]
  simp [Pi.single_apply, Fin.succ_inj]

/-- The face embedding `faceEmbed : ℝⁿ → ℝⁿ⁺¹`, which includes `ℝⁿ` as the boundary face
of the half-space, is continuous. -/
theorem continuous_face_embed :
    Continuous (faceEmbed : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin (n + 1))) := by
  unfold Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed
  refine continuous_finsetSum _ fun i _ => Continuous.smul ?_ continuous_const
  exact (EuclideanSpace.proj (𝕜 := ℝ) i).continuous

end Library.Geometry.ManifoldBdry.FaceMap
