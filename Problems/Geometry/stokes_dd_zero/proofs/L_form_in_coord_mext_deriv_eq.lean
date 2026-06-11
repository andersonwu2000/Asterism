-- Direct proof from Library's mext_deriv_triv_read: unfold formInCoord at
-- p := (extChartAt I x₀).symm y, rewrite the trivialization read via
-- continuousLinearMapAt_apply_of_mem, apply mext_deriv_triv_read, and close
-- with (extChartAt I x₀).right_inv hy.
import Mathlib
import Problems.Geometry.stokes_dd_zero.Defs
import Problems.Geometry.stokes_dd_zero.proofs._strategy_s11696

namespace Problems.Geometry.stokes_dd_zero

def form_in_coord_mext_deriv_eq := @Problems.Geometry.stokes_dd_zero.s11696

end Problems.Geometry.stokes_dd_zero
