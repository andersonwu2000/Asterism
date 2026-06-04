import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- dvd_five_mul_ten_factorial_factorization_five_le_three: contrapose via 5^4 ∤ 5*10!
-- Any divisor of 5*10! = 2^8·3^4·5^3·7 has 5-adic valuation ≤ 3;
-- contrapose: if factorization 5 ≥ 4 then 5^4 ∣ m ∣ 5*10!, contradicting norm_num.
theorem dvd_five_mul_ten_factorial_factorization_five_le_three :
    ∀ m : ℕ, m ∣ 5 * 10! → m.factorization 5 ≤ 3 := by
  intro m hm
  by_contra h
  push Not at h
  have h4 : 4 ≤ m.factorization 5 := h
  have hm_ne : m ≠ 0 := (Nat.pos_of_dvd_of_pos hm (by norm_num [factorial])).ne'
  have hp5 : Nat.Prime 5 := by norm_num
  have hpow : 5 ^ 4 ∣ m := (hp5.pow_dvd_iff_le_factorization hm_ne).mpr h4
  have hdvd : 5 ^ 4 ∣ 5 * 10 ! := hpow.trans hm
  norm_num [Nat.factorial] at hdvd

end Problems.Minif2f.amc12a_2020_p21
