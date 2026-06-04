import Mathlib
import Problems.Minif2f.amc12a_2002_p12.Defs
import Problems.Minif2f.amc12a_2002_p12.proofs.L_a_eq_2_or_b_eq_2

namespace Problems.Minif2f.amc12a_2002_p12

-- Reduce to a side-fact: at least one of the two primes is 2 (odd-sum + both-prime ⇒ 2 forced).
-- Sub-goal `a_eq_2_or_b_eq_2` carries the prime-parity content; combinator splits cases and uses a+b=63 via omega.
theorem s533 : ∀ (f : ℝ → ℝ) (k : ℝ) (a b : ℕ),
    (∀ x, f x = x ^ 2 - 63 * x + k) →
    (f a = 0 ∧ f b = 0) →
    a ≠ b →
    (Nat.Prime a ∧ Nat.Prime b) →
    a + b = 63 →
    (a = 2 ∧ b = 61) ∨ (a = 61 ∧ b = 2)  := by
  intro f k a b hf hroots hab hprimes hsum
  have h2 : a = 2 ∨ b = 2 := a_eq_2_or_b_eq_2 f k a b hf hroots hab hprimes hsum
  rcases h2 with ha2 | hb2
  · left
    refine ⟨ha2, ?_⟩
    omega
  · right
    refine ⟨?_, hb2⟩
    omega

end Problems.Minif2f.amc12a_2002_p12
