import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_dvd_pow_two_three_coprime_six_eq_one
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_n_factorizes_two_three

namespace Problems.Minif2f.mathd_numbertheory_709

-- Two sub-goals + a trivial combinator.
-- A. `n_factorizes_two_three`: τ(2n)=28 ∧ τ(3n)=30 force n = 2^a * 3^b (existence form,
--    structurally bigger — the τ analysis carries the weight).
-- B. `dvd_pow_two_three_coprime_six_eq_one`: pure arithmetic — any divisor of 2^a * 3^b
--    coprime to 6 is 1, by collapsing gcd with the Coprime witness on each prime power.
-- Combinator: feed n's (a,b) factorization into the prime-power lemma at m.
theorem s9819 : ∀ (n : ℕ) (h₀ : 0 < n)
    (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
    (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
    ∀ m, m ∣ n → Nat.Coprime m 6 → m = 1  := by
  intro n h₀ h₁ h₂ m hm hcop
  obtain ⟨a, b, hn⟩ := n_factorizes_two_three n h₀ h₁ h₂
  rw [hn] at hm
  exact dvd_pow_two_three_coprime_six_eq_one a b m hm hcop
end Problems.Minif2f.mathd_numbertheory_709
