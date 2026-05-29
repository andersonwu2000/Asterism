-- Generator-1 analogue of `letter0_split`/s11482: transport the F₂ identity
-- `b·Wᵦ⁻¹ = M\Wᵦ` to point sets via the equivariant `wrd`. The bijection
-- `x ↦ φ(of 1)•x` on M has inverse `y ↦ φ((of 1)⁻¹)•y` (group/action algebra,
-- inline). Genuine content is the head-flip `key`: `hwrd` + proved sibling
-- `head_inv_mul_iff 1`. `Set.ext` + this iff close both inclusions. No sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11489

namespace Problems.Geometry.banach_tarski

def b_letter_split := @Problems.Geometry.banach_tarski.s11489

end Problems.Geometry.banach_tarski
