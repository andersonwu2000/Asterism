import Mathlib
import Problems.Minif2f.induction_divisibility_9div10tonm1.Defs

namespace Problems.Minif2f.induction_divisibility_9div10tonm1

-- Direct: 10 ≡ 1 [MOD 9], so 10^n ≡ 1^n = 1 [MOD 9], thus 9 ∣ 10^n - 1 (with 1 ≤ 10^n).
theorem s624 : ∀ (n : ℕ) (h₀ : 0 < n), 9 ∣ 10 ^ n - 1  := by
  intro n _h₀
  have h : (10 : ℕ) ≡ 1 [MOD 9] := by decide
  have h2 : (10 : ℕ) ^ n ≡ 1 ^ n [MOD 9] := h.pow n
  rw [one_pow] at h2
  exact (Nat.modEq_iff_dvd' (Nat.one_le_pow n 10 (by norm_num))).mp h2.symm

end Problems.Minif2f.induction_divisibility_9div10tonm1
