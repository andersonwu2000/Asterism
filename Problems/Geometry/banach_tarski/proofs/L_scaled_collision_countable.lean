import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- scaled_collision_countable: preimage of collision set under θ ↦ n·θ is countable
-- because it equals the image of {φ | R φ p = q} under φ ↦ φ/(n:ℝ), inheriting countability.
theorem scaled_collision_countable (D : Set E) (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    ∀ (n : ℕ), 1 ≤ n → ∀ p ∈ D, ∀ q ∈ D,
      {θ : ℝ | R ((n : ℝ) * θ) p = q}.Countable := by
  intro n hn p hp q hq
  have hn_pos : (n : ℝ) ≠ 0 := Nat.cast_ne_zero.mpr (by omega)
  have heq : {θ : ℝ | R ((n : ℝ) * θ) p = q} =
      (fun φ => φ / (n : ℝ)) '' {φ : ℝ | R φ p = q} := by
    ext θ
    simp only [Set.mem_setOf_eq, Set.mem_image]
    constructor
    · intro h
      exact ⟨(n : ℝ) * θ, h, by field_simp⟩
    · rintro ⟨φ, hφ, rfl⟩
      rwa [mul_div_cancel₀ φ hn_pos]
  rw [heq]
  exact (hcol p hp q hq).image _

end Problems.Geometry.banach_tarski
