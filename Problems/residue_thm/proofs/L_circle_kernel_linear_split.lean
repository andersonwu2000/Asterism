-- Pointwise: on the sphere, f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z)
-- (since hz puts z off the sphere, hence w - z ≠ 0). Lift via circle integral
-- linearity: integral_congr → integral_add → integral_const_mul. Sub-goals isolate
-- (a) the pointwise field identity, (b)/(c) per-summand circle-integrability.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10443

namespace Problems.residue_thm

def circle_kernel_linear_split := @Problems.residue_thm.s10443

end Problems.residue_thm
