import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_residue_16k_plus_10

namespace Problems.Minif2f.mathd_numbertheory_405

-- Decompose using Pisano periodicity: t mod 7 has period 16 for the Fibonacci-like sequence,
-- so t b % 7 depends only on b mod 16. Sub-goal: ∀ k, t (16k+10) % 7 = 6 (proved by induction on k
-- using the Fibonacci recurrence). Combine: rewrite b = 16*(b/16) + 10 from h₄.
theorem s9442 : ∀ (b : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1) (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₄ : b ≡ 10 [MOD 16]), t b % 7 = 6  := by
  intro b t h₀ h₁ h₂ h₄
  have h_periodic : ∀ k, t (16 * k + 10) % 7 = 6 :=
    t_residue_16k_plus_10 b t h₀ h₁ h₂ h₄
  have hb : b = 16 * (b / 16) + 10 := by
    have hm := h₄
    unfold Nat.ModEq at hm
    omega
  rw [hb]
  exact h_periodic (b / 16)

end Problems.Minif2f.mathd_numbertheory_405
