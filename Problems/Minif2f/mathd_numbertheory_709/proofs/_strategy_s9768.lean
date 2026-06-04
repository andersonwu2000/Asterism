import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_card_coprime_6_pow_two_pow_three_le_one
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_pow_two_three_factorization

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split into: (A) the 2-3-smooth factorization `∃ a b, n = 2^a * 3^b`
--   (full τ-analysis lives here — Backward sub-goal);
-- (B) pure ℕ-arithmetic bound on `((Nat.divisors (2^a * 3^b)).filter (Coprime · 6)).card`
--   (independent of n's hypotheses — Builder sub-goal).
-- Combinator: obtain (a, b) from (A); rewrite `n` and apply (B).
theorem s9768 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    ((Nat.divisors n).filter (fun d => Nat.Coprime d 6)).card ≤ 1  := by
  intro n h₀ h₁ h₂
  have h_pow := pow_two_three_factorization n h₀ h₁ h₂
  have h_card := card_coprime_6_pow_two_pow_three_le_one
  obtain ⟨a, b, hab⟩ := h_pow
  rw [hab]
  exact h_card a b

end Problems.Minif2f.mathd_numbertheory_709
