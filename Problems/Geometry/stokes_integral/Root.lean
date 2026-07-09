-- Pointwise-zero route: every partition-of-unity summand of `DiffForm.integral 0`
-- carries the factor `localCoeff 0 (B.c i) y`, which vanishes identically.
-- `localcoeff_zero` proves the pointwise vanishing (section coe_zero + CLM map_zero
-- + alternating-map coe_zero); `integral_zero_of_localcoeff_zero` kills the
-- partition-of-unity sum (mul_zero/zero_mul + integral_zero + finsum_zero) for ANY
-- form with vanishing localCoeff — each piece strictly simpler than the parent.
import Mathlib
import Problems.Geometry.stokes_integral.Defs
import Problems.Geometry.stokes_integral.proofs._strategy_s11711

namespace Problems.Geometry.stokes_integral

def main := @Problems.Geometry.stokes_integral.s11711

end Problems.Geometry.stokes_integral
