import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem conjugate_orbit_ne_zero (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hfix : ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c) (n : ℕ) (hn : 1 ≤ n) :
    c - (R ^ n) c ≠ 0 := by exact sub_ne_zero_of_ne fun a ↦ hfix n hn (id (Eq.symm a))

end Problems.Geometry.banach_tarski
