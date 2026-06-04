import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs

namespace Problems.Minif2f.imo_1977_p5

-- q_eq_44: q=44 follows from q²≤1977 (upper bound) and a+b≤2q+1 via QM-AM (lower bound)
theorem q_eq_44 : ∀ (a b q r : ℕ) (h₀ : r < a + b)
    (h₁ : a ^ 2 + b ^ 2 = (a + b) * q + r) (h₂ : q ^ 2 + r = 1977), q = 44 := by
  intro a b q r h₀ h₁ h₂
  have hq_le : q ≤ 44 := by nlinarith [sq_nonneg q, Nat.zero_le r]
  have hqm : (a + b) ^ 2 ≤ 2 * (a ^ 2 + b ^ 2) := by
    zify; nlinarith [sq_nonneg ((a : ℤ) - b)]
  have hab : a + b ≤ 2 * q + 1 := by nlinarith [Nat.zero_le r]
  have hr_le : r ≤ 2 * q := by omega
  have hq_lower : 1977 ≤ q ^ 2 + 2 * q := by nlinarith
  interval_cases q <;> omega

end Problems.Minif2f.imo_1977_p5
