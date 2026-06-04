import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs

namespace Problems.Minif2f.imo_1964_p1_1

-- h_period: 7 | 2^(n+3) - 1 → 7 | 2^n - 1, using 8·2^n - 1 = 7·2^n + (2^n - 1)
-- Nat.dvd_sub removes the 7·2^n term; omega resolves the ℕ-subtraction identity.
theorem h_period : ∀ (n : ℕ), 7 ∣ 2 ^ (n + 3) - 1 → 7 ∣ 2 ^ n - 1 := by
  intro n h
  have h1 : 2 ^ (n + 3) = 8 * 2 ^ n := by ring
  rw [h1] at h
  have h2 : 7 ∣ 7 * 2 ^ n := dvd_mul_right 7 (2 ^ n)
  have hm : 2 ^ n ≥ 1 := Nat.one_le_pow n 2 (by norm_num)
  have h5 : 7 ∣ (8 * 2 ^ n - 1) - 7 * 2 ^ n := Nat.dvd_sub h h2
  have h6 : (8 * 2 ^ n - 1) - 7 * 2 ^ n = 2 ^ n - 1 := by omega
  rw [h6] at h5
  exact h5

alias period := h_period

end Problems.Minif2f.imo_1964_p1_1
