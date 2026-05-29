-- Transport the F₂ identity `a·Wₐ⁻¹ = F₂\Wₐ` to point sets via the equivariant `wrd`.
-- The bijection `x ↦ φ(of 0)•x` on M has inverse `y ↦ φ((of 0)⁻¹)•y` (group/action algebra,
-- inline). Its only genuine-math content is the head-flip `letter0_head_flip`: for z∈M, the
-- word of `φ((of 0)⁻¹)•z` starts with `(0,false)` iff that of `z` does not start with `(0,true)`
-- (just `hwrd` + the proved sibling `head_inv_mul_iff`). Set.ext + this iff close both inclusions.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11482

namespace Problems.Geometry.banach_tarski

def letter0_split := @Problems.Geometry.banach_tarski.s11482

end Problems.Geometry.banach_tarski
