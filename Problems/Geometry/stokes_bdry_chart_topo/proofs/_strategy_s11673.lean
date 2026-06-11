import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs

namespace Problems.Geometry.stokes_bdry_chart_topo

open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier
open Library.Geometry.ManifoldBoundary.Defs

-- Direct coordinate computation: after `ext i`, both sides reduce to the `i.succ`
-- coordinate of the basis expansion; `Fin.succ` injectivity collapses the sum.
theorem s11673 (z : EuclideanSpace ℝ (Fin n)) :
    faceProj (faceEmbed z) = z  := by
  ext i
  simp only [Library.Geometry.ManifoldBoundary.Defs.faceProj,
    Library.Geometry.ManifoldBoundary.HalfSpaceFrontier.faceEmbed,
    EuclideanSpace.basisFun_apply]
  simp [Pi.single_apply, Fin.succ_inj]

end Problems.Geometry.stokes_bdry_chart_topo
