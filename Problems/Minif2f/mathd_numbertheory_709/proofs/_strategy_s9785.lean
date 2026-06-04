import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_factorize_when_two_three_smooth
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_n_smooth_at_two_three

namespace Problems.Minif2f.mathd_numbertheory_709

-- (1) prove n is 2,3-smooth (only primes dividing n are 2 or 3): the full τ-analysis
--     on τ(2n)=28 and τ(3n)=30 forces the coprime-to-6 part of n to have one divisor;
-- (2) lift smoothness to existence of (a, b) with n = 2^a * 3^b via the standard
--     factorization (this matches the already-proved `exists_two_three_factorization`).
-- Combinator: apply (2) to the smoothness fact produced by (1).
theorem s9785 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    ∃ a b, n = 2 ^ a * 3 ^ b  := by
  intro n h₀ h₁ h₂
  have h_smooth := n_smooth_at_two_three n h₀ h₁ h₂
  exact factorize_when_two_three_smooth n h₀ h₁ h₂ h_smooth

end Problems.Minif2f.mathd_numbertheory_709
