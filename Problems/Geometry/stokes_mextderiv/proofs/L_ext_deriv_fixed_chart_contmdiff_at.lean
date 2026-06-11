-- Bridge extDerivWithin from (range I) to (extChartAt I x₀).target by set-locality
-- [sub-goal ext_deriv_within_eq_of_mem_nhds_within], get ContDiffOn on target from
-- form_in_coord_smooth + ext_deriv_within_smooth + uniqueDiffOn_extChartAt_target,
-- then compose with the smooth chart map and localize at x₀.
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11691

namespace Problems.Geometry.stokes_mextderiv

def ext_deriv_fixed_chart_contmdiff_at := @Problems.Geometry.stokes_mextderiv.s11691

end Problems.Geometry.stokes_mextderiv
