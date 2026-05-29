import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem length_pow_inv_of (k : ℕ) :
    (FreeGroup.toWord (((FreeGroup.of (1:Fin 2))⁻¹) ^ k)).length = k := by norm_num

end Problems.Geometry.banach_tarski
