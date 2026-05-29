import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Backward
theorem exists_rotation_shift_disjoint (D : Set E) (hD : D.Countable) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧ ∀ n : ℕ, 1 ≤ n → Disjoint ((ρ ^ n) '' D) D := by sorry

end Problems.Geometry.banach_tarski
