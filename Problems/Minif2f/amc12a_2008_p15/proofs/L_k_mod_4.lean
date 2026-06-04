import Mathlib
namespace Problems.Minif2f.amc12a_2008_p15

-- k_mod_4: 4 divides 2008^2 + 2^2008 via Nat.pow_dvd_pow for 2^2008 and norm_num for 2008^2
-- 2008^2: 4 | 2008 (= 4*502), so 4 | 2008^2 by norm_num.
-- 2^2008: 2^2 | 2^2008 by Nat.pow_dvd_pow since 2 ≤ 2008; simpa rewrites 2^2 = 4.
theorem k_mod_4 : ∀ (k : ℕ) (h₀ : k = 2008 ^ 2 + 2 ^ 2008), k % 4 = 0 := by
  intro k h₀
  rw [h₀]
  have h1 : 4 ∣ 2008 ^ 2 := by norm_num
  have h2 : 4 ∣ 2 ^ 2008 := by
    have : 2 ^ 2 ∣ 2 ^ 2008 := Nat.pow_dvd_pow 2 (by norm_num)
    simpa using this
  have h3 : 4 ∣ 2008 ^ 2 + 2 ^ 2008 := Nat.dvd_add h1 h2
  obtain ⟨m, hm⟩ := h3
  omega

end Problems.Minif2f.amc12a_2008_p15
