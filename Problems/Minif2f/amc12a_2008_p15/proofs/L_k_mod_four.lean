import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- k_mod_four: 4 divides each of 2008^2 (norm_num) and 2^2008 (Nat.pow_dvd_pow), so 4 ∣ k
theorem k_mod_four : ∀ (k : ℕ) (h₀ : k = 2008 ^ 2 + 2 ^ 2008), k % 4 = 0 := by
  intro k h₀
  have h1 : 4 ∣ 2008 ^ 2 := by norm_num
  have h2 : 4 ∣ 2 ^ 2008 := by
    have := Nat.pow_dvd_pow 2 (show 2 ≤ 2008 by norm_num)
    simpa using this
  have h3 : 4 ∣ k := h₀ ▸ dvd_add h1 h2
  exact Nat.dvd_iff_mod_eq_zero.mp h3

end Problems.Minif2f.amc12a_2008_p15
