import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- two_pow_p_sub_one_eq_one: Fermat's little theorem — (2 : ZMod p)^(p-1) = 1
-- for prime p ≥ 5 (so p ∤ 2). Uses ZMod.pow_card_sub_one_eq_one with Fact p.Prime;
-- non-zero witness: p ∣ 2 ⇒ p ≤ 2 contradicts p ≥ 5.
theorem two_pow_p_sub_one_eq_one :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → (2 : ZMod p) ^ (p - 1) = 1 := by
  intro m hm hdvd h3 h9 h7 p hp h5 hpm
  haveI : Fact p.Prime := ⟨hp⟩
  apply ZMod.pow_card_sub_one_eq_one
  intro h
  have h2 : p ∣ 2 := by
    have : ((2 : ℕ) : ZMod p) = 0 := by exact_mod_cast h
    rwa [CharP.cast_eq_zero_iff (ZMod p) p] at this
  have hle : p ≤ 2 := Nat.le_of_dvd (by norm_num) h2
  omega

end Problems.Minif2f.imo_1990_p3
