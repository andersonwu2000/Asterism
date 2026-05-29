-- Power law for the z-rotation block by induction on `n`, reusing the proved
-- multiplication law `s11436 : M(α)·M(β) = M(α+β)`.
-- Base `n=0`: `M^0 = 1 = M(0)`. Step: `M^(k+1) = M^k·M = M(kθ)·M(θ) = M((k+1)θ)`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11445

namespace Problems.Geometry.banach_tarski

def z_rotation_matrix_pow := @Problems.Geometry.banach_tarski.s11445

end Problems.Geometry.banach_tarski
