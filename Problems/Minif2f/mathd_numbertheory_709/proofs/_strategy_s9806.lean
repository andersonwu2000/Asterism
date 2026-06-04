import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_coprime_to_6_div_eq_one_2
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_prime_div_two_or_three_of_smooth_2

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split into: (A) every divisor of n coprime to 6 must equal 1
--   (the τ(2n)=28 ∧ τ(3n)=30 ⇒ coprime-to-6 part is τ=1 work);
-- (B) the structural step: a prime p ≠ 2, 3 is coprime to 6, so under (A) it
--   cannot divide n.
-- Combinator: feed (A) into (B) at this specific n.
theorem s9806 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    ∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3  := by
  intro n h₀ h₁ h₂
  have h_smooth := coprime_to_6_div_eq_one_2 n h₀ h₁ h₂
  exact prime_div_two_or_three_of_smooth_2 n h₀ h₁ h₂ h_smooth

end Problems.Minif2f.mathd_numbertheory_709
