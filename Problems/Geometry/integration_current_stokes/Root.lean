-- Currents boundary identity ∂[[e]] = [[∂e]] on a flat test form; two-citation leaf-bypass.
-- Unfold both currents to DiffForm.integral, rewrite LHS via d-naturality of the flat pullback
-- (mextDeriv_pullbackFlatForm, right-to-left), then close with the per-bump Stokes keystone
-- integral_mextDeriv_eq_integral_pullbackBdry applied to pullbackFlatForm e ψ he hψ.
import Mathlib
import Problems.Geometry.integration_current_stokes.Defs
import Problems.Geometry.integration_current_stokes.proofs._strategy_s17824

namespace Problems.Geometry.integration_current_stokes

def main := @Problems.Geometry.integration_current_stokes.s17824

end Problems.Geometry.integration_current_stokes
