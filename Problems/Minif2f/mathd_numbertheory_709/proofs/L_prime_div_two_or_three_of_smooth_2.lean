import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_709

-- prime_div_two_or_three_of_smooth_2: if every divisor of n coprime to 6 is 1, then
-- any prime dividing n is 2 or 3 (structural step: prime p ≠ 2, 3 is coprime to 6,
-- so hsmooth forces p = 1, contradicting primality)
theorem prime_div_two_or_three_of_smooth_2 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    (∀ m, m ∣ n → Nat.Coprime m 6 → m = 1) →
    ∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3 := by
  intro n h₀ h₁ h₂ hsmooth p hp hdvd
  rcases eq_or_ne p 2 with rfl | hne2
  · exact Or.inl rfl
  rcases eq_or_ne p 3 with rfl | hne3
  · exact Or.inr rfl
  exfalso
  have hcop : Nat.Coprime p 6 := by
    apply hp.coprime_iff_not_dvd.mpr
    intro h6
    have h23 : p ∣ 2 * 3 := by simpa using h6
    rcases hp.dvd_mul.mp h23 with h2 | h3
    · exact hne2 (Nat.le_antisymm (Nat.le_of_dvd (by norm_num) h2) hp.two_le)
    · have hle3 : p ≤ 3 := Nat.le_of_dvd (by norm_num) h3
      have hge2 : 2 ≤ p := hp.two_le
      interval_cases p
      · exact hne2 rfl
      · exact hne3 rfl
  exact absurd (hsmooth p hdvd hcop) hp.one_lt.ne'

end Problems.Minif2f.mathd_numbertheory_709
