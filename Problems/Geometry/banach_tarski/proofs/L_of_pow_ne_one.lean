import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem of_pow_ne_one : ∀ n : ℕ, 1 ≤ n → (FreeGroup.of (0 : Fin 2)) ^ n ≠ 1 := by aesop

end Problems.Geometry.banach_tarski
