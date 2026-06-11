-- Reduce continuity of `chartInvFun` to continuity of `(extChartAt _ p.val).symm ∘ faceEmbed`
-- via the subtype-inducing map `Subtype.val : Bdry n M → M`: on `chartTarget p` the `dite`
-- in `chartInvFun` always takes the then-branch (sub-goal 1, value identity), and the
-- then-branch composite is continuous on `chartTarget p` (sub-goal 2).
-- `IsInducing.continuousOn_iff` + `ContinuousOn.congr` combine the two.
import Mathlib
import Problems.Geometry.stokes_bdry_chart_topo.Defs
import Problems.Geometry.stokes_bdry_chart_topo.proofs._strategy_s11677

namespace Problems.Geometry.stokes_bdry_chart_topo

def chart_inv_fun_continuous_on := @Problems.Geometry.stokes_bdry_chart_topo.s11677

end Problems.Geometry.stokes_bdry_chart_topo
