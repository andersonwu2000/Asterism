import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_coprime_to_six_div_one
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_smooth_implies_prime_two_or_three

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split: (A) every divisor of n coprime to 6 equals 1 (τ(2n)=28 ∧ τ(3n)=30 ⇒
--   coprime-to-6 divisors have τ=1); (B) structural step — a prime p ≠ 2, 3 is
--   coprime to 6, so (A) forces p = 1, contradicting primality.
-- Combinator: feed (A)'s smoothness witness into (B) at this specific n.
theorem s9834 :
    ∀ (n : ℕ) (h₀ : 0 < n)
      (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      ∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3  := by
  intro n h₀ h₁ h₂
  have h_smooth := coprime_to_six_div_one
  have h_struct := smooth_implies_prime_two_or_three
  exact h_struct n h₀ h₁ h₂ (h_smooth n h₀ h₁ h₂)

end Problems.Minif2f.mathd_numbertheory_709
