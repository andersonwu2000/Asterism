import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_rotation_word_ne_one_of_reduced

namespace Problems.Geometry.banach_tarski

-- entry_kind: Backward
theorem zrot_collision_family :
    ∃ R0 : ℝ → (E ≃ᵢ E),
      (∀ t : ℝ, R0 t 0 = 0) ∧
      (∀ (t : ℝ) (n : ℕ), (R0 t) ^ n = R0 ((n : ℝ) * t)) ∧
      (∀ p : E, ¬ (p 0 = 0 ∧ p 1 = 0) → ∀ q : E, {t : ℝ | R0 t p = q}.Countable) := by apply rotation_word_ne_one_of_reduced <;> assumption

end Problems.Geometry.banach_tarski
