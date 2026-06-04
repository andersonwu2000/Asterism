import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- prime_div_two_or_three_of_smooth: if every divisor of n coprime to 6 is 1,
-- then any prime divisor of n must be 2 or 3; proved by showing a prime p ≠ 2, 3
-- is coprime to 6 (via Nat.Prime.coprime_iff_not_dvd), forcing p = 1 ⊥ p.Prime.
theorem prime_div_two_or_three_of_smooth : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    (∀ m, m ∣ n → Nat.Coprime m 6 → m = 1) →
    ∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3 := by
  intro n _h₀ _h₁ _h₂ hsmooth p hp hdvd
  by_contra hne
  push Not at hne
  obtain ⟨hp2, hp3⟩ := hne
  have hndvd2 : ¬ p ∣ 2 := fun h =>
    hp2 ((Nat.prime_two.eq_one_or_self_of_dvd p h).resolve_left (Nat.Prime.one_lt hp).ne')
  have hndvd3 : ¬ p ∣ 3 := fun h =>
    hp3 ((Nat.prime_three.eq_one_or_self_of_dvd p h).resolve_left (Nat.Prime.one_lt hp).ne')
  have hcop : Nat.Coprime p 6 := by
    rw [show (6 : ℕ) = 2 * 3 from by norm_num]
    exact (hp.coprime_iff_not_dvd.mpr hndvd2).mul_right (hp.coprime_iff_not_dvd.mpr hndvd3)
  exact (Nat.Prime.one_lt hp).ne' (hsmooth p hdvd hcop)

end Problems.Minif2f.mathd_numbertheory_709
