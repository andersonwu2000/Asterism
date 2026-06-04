import Mathlib
import Problems.Minif2f.mathd_numbertheory_156.Defs

namespace Problems.Minif2f.mathd_numbertheory_156

-- Direct: gcd(n+7, 2n+1) divides both n+7 and 2n+1, hence divides 2*(n+7) - (2n+1) = 13.
-- No sub-goals — leaf-bypass: `Nat.dvd_sub` (2-arg version in this toolchain) closes it.
theorem s9306 : ∀ (n : ℕ) (h₀ : 0 < n), Nat.gcd (n + 7) (2 * n + 1) ≤ 13  := by
  intro n h₀
  have h1 : Nat.gcd (n+7) (2*n+1) ∣ (n+7) := Nat.gcd_dvd_left _ _
  have h2 : Nat.gcd (n+7) (2*n+1) ∣ (2*n+1) := Nat.gcd_dvd_right _ _
  have h3 : Nat.gcd (n+7) (2*n+1) ∣ 2*(n+7) := h1.mul_left 2
  have heq : 13 = 2*(n+7) - (2*n+1) := by omega
  have hdvd : Nat.gcd (n+7) (2*n+1) ∣ 13 := by
    rw [heq]; exact Nat.dvd_sub h3 h2
  exact Nat.le_of_dvd (by norm_num) hdvd

end Problems.Minif2f.mathd_numbertheory_156
