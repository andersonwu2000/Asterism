import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_factorize_when_two_three_smooth_2
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_n_smooth_at_two_three_2

namespace Problems.Minif2f.mathd_numbertheory_709

-- (1) `n_smooth_at_two_three_2`: only primes dividing n are 2 or 3 (the τ-analysis carries
--     all the weight here — structurally bigger, Backward-style).
-- (2) `factorize_when_two_three_smooth_2`: lift smoothness to existence of (a, b)
--     by choosing a := v₂(n), b := v₃(n) via the factorization equation.
-- Combinator: apply (2) to the smoothness witness produced by (1).
theorem s9828 :
    ∀ (n : ℕ) (h₀ : 0 < n)
      (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      ∃ a b, n = 2 ^ a * 3 ^ b  := by
  intro n h₀ h₁ h₂
  have h_smooth := n_smooth_at_two_three_2 n h₀ h₁ h₂
  exact factorize_when_two_three_smooth_2 n h₀ h₁ h₂ h_smooth

end Problems.Minif2f.mathd_numbertheory_709
