import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_periodic_16k_plus_10

namespace Problems.Minif2f.mathd_numbertheory_405

-- Decompose abstract Pisano-periodicity `∀ a ≡ 10 [MOD 16], t a % 7 = t 10 % 7` into:
-- (1) `t_periodic_16k_plus_10`: `∀ k, t (16*k + 10) % 7 = t 10 % 7` (concrete 16k+10 form).
-- Combinator: for any a with a ≡ 10 [MOD 16], rewrite a = 16*(a/16) + 10 via
-- `Nat.div_add_mod` + omega, then apply sub-goal at k = a/16.
theorem s9671 (b : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₄ : b ≡ 10 [MOD 16]) :
    ∀ a, a ≡ 10 [MOD 16] → t a % 7 = t 10 % 7  := by
  intro a h
  have h_periodic : ∀ k, t (16 * k + 10) % 7 = t 10 % 7 :=
    t_periodic_16k_plus_10 t h₀ h₁ h₂
  have h_form : a = 16 * (a / 16) + 10 := by
    have hmod : a % 16 = 10 := by unfold Nat.ModEq at h; omega
    have := Nat.div_add_mod a 16
    omega
  calc t a % 7
      = t (16 * (a / 16) + 10) % 7 := by rw [← h_form]
    _ = t 10 % 7 := h_periodic (a / 16)

end Problems.Minif2f.mathd_numbertheory_405
