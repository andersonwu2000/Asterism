import Mathlib
import Problems.Minif2f.amc12a_2016_p2.Defs

namespace Problems.Minif2f.amc12a_2016_p2

-- pow_eq_gives_three: rpow injectivity via Real.rpow_lt_rpow_of_exponent_lt;
-- rewrite 1000^5 as 10^15 (rpow), then use StrictMono.injective at base 10.
theorem pow_eq_gives_three : ∀ (x : ℝ), (10 : ℝ)^(5*x) = (1000 : ℝ)^5 → x = 3 := by
  intro x h
  have h15 : (1000 : ℝ) ^ (5 : ℕ) = (10 : ℝ) ^ (15 : ℝ) := by
    norm_num [Real.rpow_natCast]
  have h2 : (10 : ℝ) ^ (5 * x) = (10 : ℝ) ^ (15 : ℝ) := by rw [← h15]; exact h
  have hinj : StrictMono ((10 : ℝ) ^ · : ℝ → ℝ) :=
    fun a b hab => Real.rpow_lt_rpow_of_exponent_lt (by norm_num) hab
  have h5x : 5 * x = 15 := hinj.injective h2
  linarith

end Problems.Minif2f.amc12a_2016_p2
