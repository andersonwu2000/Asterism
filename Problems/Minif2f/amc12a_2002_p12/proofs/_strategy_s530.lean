import Mathlib
import Problems.Minif2f.amc12a_2002_p12.Defs
import Problems.Minif2f.amc12a_2002_p12.proofs.L_prime_pair_sum_63
import Problems.Minif2f.amc12a_2002_p12.proofs.L_vieta_sum

namespace Problems.Minif2f.amc12a_2002_p12

-- Vieta: f(a)=f(b)=0 with a≠b ⇒ a+b = 63 (sum of roots from quadratic identity).
-- Then odd-sum-of-two-primes ⇒ one is 2, the other is 61.
theorem s530 : ∀ (f : ℝ → ℝ) (k : ℝ) (a b : ℕ),
    (∀ x, f x = x ^ 2 - 63 * x + k) →
    (f a = 0 ∧ f b = 0) →
    a ≠ b →
    (Nat.Prime a ∧ Nat.Prime b) →
    (a = 2 ∧ b = 61) ∨ (a = 61 ∧ b = 2)  := by
  intro f k a b hf hzero hab hp
  have h_sum : a + b = 63 := vieta_sum f k a b hf hzero hab hp
  exact prime_pair_sum_63 f k a b hf hzero hab hp h_sum

end Problems.Minif2f.amc12a_2002_p12
