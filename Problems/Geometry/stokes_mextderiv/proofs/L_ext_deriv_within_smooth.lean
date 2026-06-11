-- extDerivWithin form s = alternatizeUncurryFinCLM ∘ fderivWithin ℝ form s;
-- the CLM is C^∞ and fderivWithin of a C^∞ family is C^∞ on s (UniqueDiffOn, ∞+1 = ∞).
import Mathlib
import Problems.Geometry.stokes_mextderiv.Defs
import Problems.Geometry.stokes_mextderiv.proofs._strategy_s11686

namespace Problems.Geometry.stokes_mextderiv

def ext_deriv_within_smooth := @Problems.Geometry.stokes_mextderiv.s11686

end Problems.Geometry.stokes_mextderiv
