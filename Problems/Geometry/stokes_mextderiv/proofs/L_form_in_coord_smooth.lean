-- formInCoord is the trivialized section (p ↦ continuousLinearMapAt at x₀'s triv of φ p)
-- precomposed with (extChartAt I x₀).symm. Sub-goal: that trivialized section is
-- ContMDiffOn on (chartAt H x₀).source. Combine with mathlib's contMDiffOn_extChartAt_symm
-- (chart inverse smooth on target, mapping into the chart source) via ContMDiffOn.comp,
-- then bridge to ContDiffOn with contMDiffOn_iff_contDiffOn (both sides vector spaces).
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11685

namespace Problems.Geometry.stokes_mextderiv

def form_in_coord_smooth := @Problems.Geometry.stokes_mextderiv.s11685

end Problems.Geometry.stokes_mextderiv
