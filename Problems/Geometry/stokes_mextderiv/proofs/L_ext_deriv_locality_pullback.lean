-- Locality: the proved sibling form_in_coord_pullback (roles of x, x₀ swapped) gives the
-- pointwise identity formInCoord I φ x₀ y = pullback form, valid on the set
-- (extChartAt I x₀).target ∩ (extChartAt I x₀).symm ⁻¹' (chartAt H x).source, which is a
-- 𝓝[range I]-neighborhood of extChartAt I x₀ x; Filter.EventuallyEq.extDerivWithin_eq
-- transports the equality through extDerivWithin.
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11694

namespace Problems.Geometry.stokes_mextderiv

def ext_deriv_locality_pullback := @Problems.Geometry.stokes_mextderiv.s11694

end Problems.Geometry.stokes_mextderiv
