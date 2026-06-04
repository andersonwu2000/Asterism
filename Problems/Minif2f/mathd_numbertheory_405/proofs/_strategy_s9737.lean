import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pair_inv_period_16_17_mod_7

namespace Problems.Minif2f.mathd_numbertheory_405

-- Strengthen to a pair invariant `t (n+16) ≡ t n` ∧ `t (n+17) ≡ t (n+1)` mod 7,
-- which lets simple induction lift the pair forward via the Fibonacci recurrence at n+18.
-- The combinator extracts the first conjunct.
theorem s9737 (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) :
    ∀ n, t (n + 16) % 7 = t n % 7  := by
  intro n
  have h_pair := pair_inv_period_16_17_mod_7 t h₀ h₁ h₂
  exact (h_pair n).1

end Problems.Minif2f.mathd_numbertheory_405
