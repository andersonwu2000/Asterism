-- Direct set-extensionality leaf: the cone over the unit sphere with radii in (0,1]
-- is exactly the punctured closed unit ball. (⊆) `‖r•x‖ = r·1 = r ≤ 1` and `r•x ≠ 0`
-- since `r > 0`, `‖x‖ = 1`; (⊇) for `y ≠ 0`, take `r = ‖y‖ ∈ (0,1]`, `x = ‖y‖⁻¹•y`
-- (`‖x‖ = 1`), then `‖y‖ • ‖y‖⁻¹ • y = y`. Pure normed-space algebra — no sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11488

namespace Problems.Geometry.banach_tarski

def cone_over_sphere_eq_punctured_ball := @Problems.Geometry.banach_tarski.s11488

end Problems.Geometry.banach_tarski
