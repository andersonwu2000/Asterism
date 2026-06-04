import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- two_pow_two_n_eq_one_mod_p: from p ∣ n and n²∣2^n+1, get 2^n≡-1 (mod p),
-- so 2^(2n)=(2^n)²=(-1)²=1 in ZMod p.
theorem two_pow_two_n_eq_one_mod_p :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ n → (2 : ZMod p) ^ (2 * n) = 1 := by
  intro n _hn2 hdvd _h3 _h9 p hp _h5 hpn
  haveI : Fact p.Prime := ⟨hp⟩
  have hpn2 : p ∣ n ^ 2 := dvd_pow hpn (by norm_num)
  have hp2n1 : p ∣ 2 ^ n + 1 := hpn2.trans hdvd
  have hn1 : (2 : ZMod p) ^ n + 1 = 0 := by
    have h : ((2 ^ n + 1 : ℕ) : ZMod p) = 0 := by
      rw [CharP.cast_eq_zero_iff (ZMod p) p]; exact hp2n1
    simpa using h
  have hneg1 : (2 : ZMod p) ^ n = -1 := by linear_combination hn1
  rw [show 2 * n = n + n from by ring, pow_add, hneg1]
  ring

end Problems.Minif2f.imo_1990_p3
