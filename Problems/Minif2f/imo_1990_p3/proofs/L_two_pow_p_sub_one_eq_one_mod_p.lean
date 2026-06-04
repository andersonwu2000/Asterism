import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- two_pow_p_sub_one_eq_one_mod_p: Fermat's little theorem — 2^(p-1) ≡ 1 (mod p) for prime p ≥ 5
-- Uses ZMod.pow_card_sub_one_eq_one; 2 ≠ 0 mod p since p ≥ 5 > 2.
theorem two_pow_p_sub_one_eq_one_mod_p :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ n → (2 : ZMod p) ^ (p - 1) = 1 := by
  intro n _hn _hsq _h3 _h9 p hp _h5 _hdvd
  haveI : Fact p.Prime := ⟨hp⟩
  have h2_ne : (2 : ZMod p) ≠ 0 := by
    intro h
    have hcast : ((2 : ℕ) : ZMod p) = 0 := by exact_mod_cast h
    rw [CharP.cast_eq_zero_iff (ZMod p) p] at hcast
    have : p ≤ 2 := Nat.le_of_dvd (by norm_num) hcast
    linarith
  exact ZMod.pow_card_sub_one_eq_one h2_ne

end Problems.Minif2f.imo_1990_p3
