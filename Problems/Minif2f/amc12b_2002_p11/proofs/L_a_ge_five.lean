import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs

namespace Problems.Minif2f.amc12b_2002_p11

-- a_ge_five: prime triplet forces a ≥ 5 via a-2 ≥ 2 (prime) and a ≠ 4 (not prime)
theorem a_ge_five : ∀ (a : ℕ) (h₀ : Nat.Prime a)
    (h₂ : Nat.Prime (a + 2)) (h₃ : Nat.Prime (a - 2)), a ≥ 5 := by
  intro a h₀ h₂ h₃
  have h3 : a - 2 ≥ 2 := h₃.two_le
  have ha : a ≥ 4 := by omega
  have hne4 : a ≠ 4 := by intro h; subst h; exact absurd h₀ (by decide)
  omega

end Problems.Minif2f.amc12b_2002_p11
