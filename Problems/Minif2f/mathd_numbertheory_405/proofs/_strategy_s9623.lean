import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_periodic_16k_plus_5

namespace Problems.Minif2f.mathd_numbertheory_405

-- Pisano periodicity: reduce `t a % 7 = t 5 % 7` to one residue lemma.
-- Sub-goal `t_periodic_16k_plus_5`: ∀ k, t (16k+5) % 7 = t 5 % 7 (handled by
-- induction on k via the Fibonacci-like recurrence in h₂). Combinator:
-- `unfold Nat.ModEq at h₃; omega` to rewrite `a = 16*(a/16) + 5`, then apply.
theorem s9623 : ∀ (a : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₃ : a ≡ 5 [MOD 16]),
    t a % 7 = t 5 % 7  := by
  intro a t h₀ h₁ h₂ h₃
  have h_periodic : ∀ k, t (16 * k + 5) % 7 = t 5 % 7 :=
    t_periodic_16k_plus_5 a t h₀ h₁ h₂ h₃
  have ha : a = 16 * (a / 16) + 5 := by
    have hm := h₃
    unfold Nat.ModEq at hm
    omega
  rw [ha]
  exact h_periodic (a / 16)

end Problems.Minif2f.mathd_numbertheory_405
