import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pisano_period_16
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_15_mod_7_eq_one

namespace Problems.Minif2f.mathd_numbertheory_405

-- Reduce ∀k, t(16k+15) % 7 = 1 to (a) Pisano periodicity mod 7 with period 16
-- and (b) base case t 15 % 7 = 1; combine by induction on k.
theorem s9619 :
    ∀ (t : ℕ → ℕ),
      t 0 = 0 →
      t 1 = 1 →
      (∀ n > 1, t n = t (n - 2) + t (n - 1)) →
      ∀ k, t (16 * k + 15) % 7 = 1  := by
  intro t h0 h1 hrec k
  have hperiod : ∀ n, t (n + 16) % 7 = t n % 7 :=
    pisano_period_16 t h0 h1 hrec
  have hbase : t 15 % 7 = 1 := t_15_mod_7_eq_one t h0 h1 hrec
  induction k with
  | zero => simpa using hbase
  | succ k ih =>
    have heq : 16 * (k + 1) + 15 = (16 * k + 15) + 16 := by ring
    rw [heq, hperiod]
    exact ih

end Problems.Minif2f.mathd_numbertheory_405
