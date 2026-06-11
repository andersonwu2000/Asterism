import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs

open scoped Manifold Bundle ContDiff
open Bundle
open Library.Geometry.ManifoldBoundary.CompactBdry
open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

-- Direct proof, no sub-goals: `faceProj` unfolds to `(EuclideanSpace.equiv (Fin n) ℝ).symm`
-- applied to the coordinate-reindexing `fun w i => w i.succ`. The reindexing is continuous by
-- `continuous_pi` over the coordinate evaluations `EuclideanSpace.proj i.succ`, and the
-- `ContinuousLinearEquiv` inverse is continuous; `Continuous.comp` closes the goal by defeq.
theorem s11672 {n : ℕ} :
    Continuous (faceProj : EuclideanSpace ℝ (Fin (n + 1)) → EuclideanSpace ℝ (Fin n))  := by
  have h : Continuous (fun w : EuclideanSpace ℝ (Fin (n + 1)) => fun i : Fin n => w i.succ) :=
    continuous_pi fun i => (EuclideanSpace.proj (i.succ : Fin (n + 1))).continuous
  exact (EuclideanSpace.equiv (Fin n) ℝ).symm.continuous.comp h

end Problems.Geometry.stokes_bdry_chart_topo
