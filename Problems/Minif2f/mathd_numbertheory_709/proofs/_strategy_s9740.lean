import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_card_divisors_three_times_pow_two_three
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_card_divisors_two_times_pow_two_three
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_tau_system_solves

namespace Problems.Minif2f.mathd_numbertheory_709

-- Decompose τ(2n)=28 ∧ τ(3n)=30 ∧ n=2^a·3^b into:
--   A. τ(2·2^a·3^b) = (a+2)(b+1)   — combinatorial fact, no parent hypotheses
--   B. τ(3·2^a·3^b) = (a+1)(b+2)   — combinatorial fact, no parent hypotheses
--   C. (a+2)(b+1)=28 → (a+1)(b+2)=30 → 2^a·3^b = 864   — pure ℕ-arithmetic system
-- Combinator: subst hn, rewrite h₁ and h₂ by A/B, apply C.
theorem s9740 :
    ∀ (n : ℕ) (_h₀ : 0 < n)
      (_h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (_h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      (∀ p, p.Prime → p ∣ n → p = 2 ∨ p = 3) →
      ∀ (a b : ℕ), n = 2 ^ a * 3 ^ b → n = 864  := by
  have h_card2 := card_divisors_two_times_pow_two_three
  have h_card3 := card_divisors_three_times_pow_two_three
  have h_solve := tau_system_solves
  intro n _h₀ _h₁ _h₂ _hsmooth a b hn
  subst hn
  rw [h_card2 a b] at _h₁
  rw [h_card3 a b] at _h₂
  exact h_solve a b _h₁ _h₂

end Problems.Minif2f.mathd_numbertheory_709
