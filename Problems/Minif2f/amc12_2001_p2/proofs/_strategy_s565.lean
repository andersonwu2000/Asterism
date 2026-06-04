import Mathlib
import Problems.Minif2f.amc12_2001_p2.Defs

namespace Problems.Minif2f.amc12_2001_p2

-- Direct algebra: 10a+b = ab+a+b ⇒ a*9 = a*b, then cancel a ≥ 1 to get b = 9.
theorem s565 : ∀ (a b n : ℕ) (h₀ : 1 ≤ a ∧ a ≤ 9) (h₁ : 0 ≤ b ∧ b ≤ 9) (h₂ : n = 10 * a + b) (h₃ : n = a * b + a + b), b = 9  := by
  intro a b n h₀ _ h₂ h₃
  obtain ⟨ha, _⟩ := h₀
  have e : 10 * a + b = a * b + a + b := h₂ ▸ h₃
  have h9 : a * 9 = a * b := by linarith
  have : 9 = b := Nat.eq_of_mul_eq_mul_left ha h9
  omega

end Problems.Minif2f.amc12_2001_p2
