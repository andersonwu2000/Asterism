import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- two_pow_two_n_eq_one_mod_min_fac: p ∣ n^2 ∣ 2^n+1 gives 2^n ≡ -1 (mod p); squaring closes
theorem two_pow_two_n_eq_one_mod_min_fac :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 →
      Nat.Coprime n (Nat.minFac n - 1) →
      (2 : ZMod (Nat.minFac n))^(2*n) = 1 := by
  intro n hn hdvd hcop
  have hpn : Nat.minFac n ∣ n := Nat.minFac_dvd n
  have hpn2 : Nat.minFac n ∣ n ^ 2 := dvd_pow hpn (by norm_num)
  have hp_dvd : Nat.minFac n ∣ 2 ^ n + 1 := dvd_trans hpn2 hdvd
  have hcast : ((2 ^ n + 1 : ℕ) : ZMod (Nat.minFac n)) = 0 := by
    rw [CharP.cast_eq_zero_iff (ZMod (Nat.minFac n)) (Nat.minFac n)]
    exact hp_dvd
  have heq : (2 : ZMod (Nat.minFac n)) ^ n + 1 = 0 := by
    have := hcast; push_cast at this; exact this
  have h2n : (2 : ZMod (Nat.minFac n)) ^ n = -1 := by linear_combination heq
  rw [show 2 * n = n * 2 from by ring, pow_mul, h2n]
  ring

end Problems.Minif2f.imo_1990_p3
