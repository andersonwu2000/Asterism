import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- two_pow_min_fac_pred_eq_one: Fermat's little theorem — 2^(p-1)=1 in ZMod p
-- where p=minFac n is an odd prime (n odd since n²∣2^n+1 forces n²∣odd).
-- Shows (2:ZMod p)≠0 via CharP.cast_eq_zero_iff + p>2, then applies
-- ZMod.pow_card_sub_one_eq_one.
theorem two_pow_min_fac_pred_eq_one :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 →
      Nat.Coprime n (Nat.minFac n - 1) →
      (2 : ZMod (Nat.minFac n))^(Nat.minFac n - 1) = 1 := by
  intro n hn hdvd _hcop
  have hp : (Nat.minFac n).Prime := Nat.minFac_prime (by omega)
  have hgt2 : 2 < Nat.minFac n := by
    have hn_odd : ¬ 2 ∣ n := by
      intro h2n
      have h2n2 : 2 ∣ n ^ 2 := dvd_pow h2n two_ne_zero
      have h2 : 2 ∣ 2 ^ n + 1 := dvd_trans h2n2 hdvd
      have h2pow : 2 ∣ 2 ^ n := dvd_pow (dvd_refl 2) (by omega)
      obtain ⟨a, ha⟩ := h2pow
      obtain ⟨b, hb⟩ := h2
      omega
    have hge2 := hp.two_le
    have hne2 : Nat.minFac n ≠ 2 := fun heq => hn_odd (heq ▸ Nat.minFac_dvd n)
    omega
  haveI : Fact (Nat.minFac n).Prime := ⟨hp⟩
  have h2_ne_0 : (2 : ZMod (Nat.minFac n)) ≠ 0 := by
    intro h
    have hcast : ((2 : ℕ) : ZMod (Nat.minFac n)) = 0 := by exact_mod_cast h
    rw [CharP.cast_eq_zero_iff (ZMod (Nat.minFac n)) (Nat.minFac n)] at hcast
    exact absurd (Nat.le_of_dvd (by omega) hcast) (by omega)
  exact ZMod.pow_card_sub_one_eq_one h2_ne_0

end Problems.Minif2f.imo_1990_p3
