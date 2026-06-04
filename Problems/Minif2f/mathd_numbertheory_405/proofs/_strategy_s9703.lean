import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pisano_period_16_2

namespace Problems.Minif2f.mathd_numbertheory_405

-- Reduce `∀ k, t (16*k + 10) % 7 = t 10 % 7` to a generic Pisano period lemma
-- `∀ n, t (n + 16) % 7 = t n % 7`; combine by `induction k` with step rewrite
-- `16*(k+1)+10 = (16*k+10)+16`, then `rw [heq, hperiod]; exact ih`.
theorem s9703 (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) :
    ∀ k, t (16 * k + 10) % 7 = t 10 % 7  := by
  have hperiod : ∀ n, t (n + 16) % 7 = t n % 7 :=
    pisano_period_16_2 t h₀ h₁ h₂
  intro k
  induction k with
  | zero => simp
  | succ k ih =>
    have heq : 16 * (k + 1) + 10 = (16 * k + 10) + 16 := by ring
    rw [heq, hperiod]
    exact ih

end Problems.Minif2f.mathd_numbertheory_405
