import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- eq_seven_of_prime_ge_five_two_pow_six: if prime q ≥ 5 satisfies 2^6 = 1 in ZMod q,
-- then q = 7; proved via q ∣ 63 (from CharP bridge) + interval_cases on q ≤ 63
theorem eq_seven_of_prime_ge_five_two_pow_six :
    ∀ q, Nat.Prime q → 5 ≤ q → (2 : ZMod q)^6 = 1 → q = 7 := by
  intro q hq hge h
  haveI : Fact q.Prime := ⟨hq⟩
  have h63 : (63 : ZMod q) = 0 := by
    have eq64 : (2 : ZMod q)^6 = 64 := by norm_num
    linear_combination h - eq64
  have hdvd : q ∣ 63 := (CharP.cast_eq_zero_iff (ZMod q) q 63).mp h63
  have hle : q ≤ 63 := Nat.le_of_dvd (by norm_num) hdvd
  interval_cases q <;> norm_num at *

end Problems.Minif2f.imo_1990_p3
