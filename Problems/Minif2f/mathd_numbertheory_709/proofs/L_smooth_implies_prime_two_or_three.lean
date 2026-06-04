import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- smooth_implies_prime_two_or_three: any prime divisor of n must be 2 or 3,
-- given that every divisor of n coprime to 6 equals 1 (structural step B).
-- Proof: prime p ≠ 2, 3 is coprime to 6 (since it cannot divide 2*3),
-- so hsmooth forces p = 1, contradicting p.Prime.one_lt.
theorem smooth_implies_prime_two_or_three :
    ∀ (n : ℕ) (h₀ : 0 < n)
      (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      (∀ m, m ∣ n → Nat.Coprime m 6 → m = 1) →
      ∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3 := by
  intro n _h₀ _h₁ _h₂ hsmooth p hp hdvd
  by_contra hc
  simp only [not_or] at hc
  obtain ⟨h2, h3⟩ := hc
  have hcop : Nat.Coprime p 6 := by
    apply hp.coprime_iff_not_dvd.mpr
    intro h6
    have h6' : p ∣ 2 * 3 := by norm_num at h6 ⊢; exact h6
    rcases hp.dvd_mul.mp h6' with h | h
    · exact h2 ((by norm_num : Nat.Prime 2).eq_one_or_self_of_dvd p h |>.resolve_left hp.one_lt.ne')
    · exact h3 ((by norm_num : Nat.Prime 3).eq_one_or_self_of_dvd p h |>.resolve_left hp.one_lt.ne')
  have heq1 := hsmooth p hdvd hcop
  exact hp.one_lt.ne' heq1

end Problems.Minif2f.mathd_numbertheory_709
