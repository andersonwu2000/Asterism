import Mathlib
import Problems.Minif2f.mathd_numbertheory_126.Defs

namespace Problems.Minif2f.mathd_numbertheory_126

theorem main : ∀ (x a : ℕ) (h₀ : 0 < x ∧ 0 < a) (h₁ : Nat.gcd a 40 = x + 3) (h₂ : Nat.lcm a 40 = x * (x + 3)) (h₃ : ∀ b : ℕ, 0 < b → Nat.gcd b 40 = x + 3 ∧ Nat.lcm b 40 = x * (x + 3) → a ≤ b), a = 8 := by sorry

end Problems.Minif2f.mathd_numbertheory_126
