import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pisano_period_16_mod_7

namespace Problems.Minif2f.mathd_numbertheory_405

-- Pisano period reduction: split into a period-16 lemma and induct on k.
-- Sub-goal `pisano_period_16_mod_7`: ∀ n, t (n+16) % 7 = t n % 7
-- (induction-strengthened pair invariant on the Fibonacci-like recurrence).
-- Combinator: `induction k` with step rewrite `16*(k+1)+5 = (16*k+5)+16`
-- (by `ring`), then `rw [heq, hperiod]; exact ih`.
theorem s9672 (a : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₃ : a ≡ 5 [MOD 16]) :
    ∀ k, t (16 * k + 5) % 7 = t 5 % 7  := by
  have hperiod : ∀ n, t (n + 16) % 7 = t n % 7 :=
    pisano_period_16_mod_7 a t h₀ h₁ h₂ h₃
  intro k
  induction k with
  | zero => simp
  | succ k ih =>
    have heq : 16 * (k + 1) + 5 = (16 * k + 5) + 16 := by ring
    rw [heq, hperiod]
    exact ih

end Problems.Minif2f.mathd_numbertheory_405
