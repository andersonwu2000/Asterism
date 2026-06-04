import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pisano_pair_mod_7

namespace Problems.Minif2f.mathd_numbertheory_405

-- Strengthen to a pair invariant: both `t (m+16) ≡ t m` and `t (m+17) ≡ t (m+1)` mod 7,
-- which admits clean step-induction (Fibonacci recurrence at m+18 lifts the pair forward).
-- Combinator extracts the first conjunct at index n.
theorem s9660 :
    ∀ (t : ℕ → ℕ),
      t 0 = 0 →
      t 1 = 1 →
      (∀ n > 1, t n = t (n - 2) + t (n - 1)) →
      ∀ n, t (n + 16) % 7 = t n % 7  := by
  intro t h0 h1 hrec n
  have h_pair := pisano_pair_mod_7 t h0 h1 hrec n
  exact h_pair.1

end Problems.Minif2f.mathd_numbertheory_405
