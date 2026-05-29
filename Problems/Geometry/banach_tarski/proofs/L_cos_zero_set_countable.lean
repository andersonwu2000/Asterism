import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- cos_zero_set_countable: {θ | cos θ = 0} is countable as the image of ℤ under n ↦ (2n+1)π/2
theorem cos_zero_set_countable : {θ : ℝ | Real.cos θ = 0}.Countable := by
  have heq : {θ : ℝ | Real.cos θ = 0} = Set.range (fun k : ℤ => (2 * k + 1) * Real.pi / 2) := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_range]
    rw [Real.cos_eq_zero_iff]
    constructor
    · rintro ⟨k, hk⟩; exact ⟨k, hk.symm⟩
    · rintro ⟨k, hk⟩; exact ⟨k, hk.symm⟩
  rw [heq]
  exact Set.countable_range _

end Problems.Geometry.banach_tarski
