import Mathlib
import Problems.Minif2f.mathd_numbertheory_530.Defs

namespace Problems.Minif2f.mathd_numbertheory_530

-- lcm_div_gcd_eq_div_mul_div: split on gcd=0/pos, then use lcm_mul_right
-- + Coprime.lcm_eq_mul after expressing m = (m/d)*d, l = (l/d)*d
theorem lcm_div_gcd_eq_div_mul_div :
    ∀ (m l : ℕ), Nat.lcm m l / Nat.gcd m l = (m / Nat.gcd m l) * (l / Nat.gcd m l) := by
  intro m l
  rcases Nat.eq_zero_or_pos (Nat.gcd m l) with h | h
  · obtain ⟨hm, hl⟩ := Nat.gcd_eq_zero_iff.mp h
    simp [hm, hl]
  · set d := Nat.gcd m l with hd_def
    have hdm : d ∣ m := Nat.gcd_dvd_left m l
    have hdl : d ∣ l := Nat.gcd_dvd_right m l
    have hcop : Nat.Coprime (m / d) (l / d) := Nat.coprime_div_gcd_div_gcd h
    have hlcm : Nat.lcm m l = (m / d) * (l / d) * d := by
      conv_lhs =>
        rw [show m = m / d * d from (Nat.div_mul_cancel hdm).symm,
            show l = l / d * d from (Nat.div_mul_cancel hdl).symm]
      rw [Nat.lcm_mul_right, Nat.Coprime.lcm_eq_mul hcop]
    rw [hlcm, Nat.mul_div_cancel _ h]

end Problems.Minif2f.mathd_numbertheory_530
