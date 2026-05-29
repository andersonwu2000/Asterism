-- The radius-1/2 fixed set is the image of the radius-1 fixed set under x ↦ (1/2)•x.
-- Scale half→full by x ↦ 2•x: it injects the half-sphere fixed set into the radius-1
-- fixed set (proved finite as rotation_fixed_set_on_sphere_finite), so finiteness pulls back.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11520

namespace Problems.Geometry.banach_tarski

def fixed_set_half_sphere_finite := @Problems.Geometry.banach_tarski.s11520

end Problems.Geometry.banach_tarski
