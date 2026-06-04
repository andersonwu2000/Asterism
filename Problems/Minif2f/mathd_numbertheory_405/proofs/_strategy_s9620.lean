import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_10_mod_7_eq_6
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_period_at_10

namespace Problems.Minif2f.mathd_numbertheory_405

-- Decompose Pisano-residue periodicity at residue 10 mod 16 into:
-- (1) `t_period_at_10`: ∀ a ≡ 10 [MOD 16], t a % 7 = t 10 % 7 (abstract periodicity).
-- (2) `t_10_mod_7_eq_6`: t 10 % 7 = 6 (10-step base case from h₀/h₁/h₂).
-- Combine: for each k, 16*k+10 ≡ 10 [MOD 16] so h_per yields t (16k+10) % 7 = t 10 % 7;
-- transit through h_base. Strictly simpler: sub-goal (1) is more abstract (any a, not 16k+10
-- form) and sub-goal (2) is a 10-step recurrence unfold (pure Builder leaf).
theorem s9620 (b : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₄ : b ≡ 10 [MOD 16]) :
    ∀ k, t (16 * k + 10) % 7 = 6  := by
  intro k
  have h_per := t_period_at_10 b t h₀ h₁ h₂ h₄
  have h_base := t_10_mod_7_eq_6 b t h₀ h₁ h₂ h₄
  have hmod : (16 * k + 10) ≡ 10 [MOD 16] := by
    unfold Nat.ModEq
    omega
  exact (h_per (16 * k + 10) hmod).trans h_base

end Problems.Minif2f.mathd_numbertheory_405
