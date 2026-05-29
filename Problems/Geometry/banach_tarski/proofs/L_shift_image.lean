import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- shift_image: pushing ρ through ⋃ₙ ρⁿ''D shifts the index by 1, via pow_add + mul_apply rfl
theorem shift_image (D : Set E) (ρ : E ≃ᵢ E) :
    ρ '' (⋃ n : ℕ, (ρ ^ n) '' D) = ⋃ n : ℕ, (ρ ^ (n+1)) '' D := by
  simp only [Set.image_iUnion]
  congr 1; ext n
  rw [Set.image_image]
  have : ρ ^ (n + 1) = ρ * ρ ^ n := by
    rw [show n + 1 = 1 + n from by omega, pow_add, pow_one]
  rw [this]; rfl

end Problems.Geometry.banach_tarski
