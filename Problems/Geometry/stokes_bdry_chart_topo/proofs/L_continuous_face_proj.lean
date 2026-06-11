-- Direct proof, no sub-goals: `faceProj` unfolds to `(EuclideanSpace.equiv (Fin n) ℝ).symm`
-- applied to the coordinate-reindexing `fun w i => w i.succ`. The reindexing is continuous by
-- `continuous_pi` over the coordinate evaluations `EuclideanSpace.proj i.succ`, and the
-- `ContinuousLinearEquiv` inverse is continuous; `Continuous.comp` closes the goal by defeq.
import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs._strategy_s11672

namespace Problems.Geometry.stokes_bdry_chart_topo

def continuous_face_proj := @Problems.Geometry.stokes_bdry_chart_topo.s11672

end Problems.Geometry.stokes_bdry_chart_topo
