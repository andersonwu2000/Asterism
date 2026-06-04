import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_5_mod_7_eq_5
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_eq_t_5_mod_7

namespace Problems.Minif2f.mathd_numbertheory_405

-- Decompose `t a % 7 = 5` via Pisano period 16 mod 7:
-- (1) `t_eq_t_5_mod_7`: t a % 7 = t 5 % 7 from a ≡ 5 [MOD 16] (periodicity).
-- (2) `t_5_mod_7_eq_5`: t 5 % 7 = 5 by recurrence unfolding from h₀, h₁, h₂.
-- Combinator: `Eq.trans`.
theorem s9444 : ∀ (a : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₃ : a ≡ 5 [MOD 16]),
    t a % 7 = 5  := by
  intro a t h₀ h₁ h₂ h₃
  have h_period := t_eq_t_5_mod_7 a t h₀ h₁ h₂ h₃
  have h_base := t_5_mod_7_eq_5 a t h₀ h₁ h₂ h₃
  exact h_period.trans h_base

end Problems.Minif2f.mathd_numbertheory_405
