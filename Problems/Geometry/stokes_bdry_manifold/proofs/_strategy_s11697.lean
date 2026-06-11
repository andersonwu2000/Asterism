import Mathlib
import Problems.Geometry.stokes_bdry_manifold.Defs

namespace Problems.Geometry.stokes_bdry_manifold

open scoped Manifold ContDiff
open Library.Geometry.ManifoldBoundary.Defs

-- Direct proof: `faceProj` is the continuous linear map `w ↦ (w ∘ Fin.succ)` transported
-- through `EuclideanSpace.equiv`; smoothness is `contDiff_pi` over coordinate projections
-- composed with the smooth linear equivalence — no sub-goals needed (leaf bypass).
theorem s11697 {n : ℕ} :
    ContDiff ℝ ∞ (faceProj (n := n))  := by
  have h : ContDiff ℝ ∞ (fun w : EuclideanSpace ℝ (Fin (n + 1)) => fun i : Fin n => w i.succ) :=
    contDiff_pi.2 fun i => (EuclideanSpace.proj (i.succ : Fin (n + 1)) (𝕜 := ℝ)).contDiff
  exact ((EuclideanSpace.equiv (Fin n) ℝ).symm.contDiff).comp h

end Problems.Geometry.stokes_bdry_manifold
