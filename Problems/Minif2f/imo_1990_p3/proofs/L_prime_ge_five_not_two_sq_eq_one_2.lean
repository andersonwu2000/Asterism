import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- prime_ge_five_not_two_sq_eq_one_2: (2:ZMod p)^2=1 forces 3=0 in ZMod p, giving p∣3,
-- contradicting p≥5 via Nat.le_of_dvd + omega.
theorem prime_ge_five_not_two_sq_eq_one_2 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → (2 : ZMod p) ^ 2 = 1 → False := by
  intro n hn hdvd h3 h9 p hp hge hzmod
  have h3z : (3 : ZMod p) = 0 := by linear_combination hzmod
  have hdvd3 : p ∣ 3 := by
    have hcast : ((3 : ℕ) : ZMod p) = 0 := by exact_mod_cast h3z
    exact (CharP.cast_eq_zero_iff (ZMod p) p 3).mp hcast
  have hle : p ≤ 3 := Nat.le_of_dvd (by norm_num) hdvd3
  omega

end Problems.Minif2f.imo_1990_p3
