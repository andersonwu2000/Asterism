import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pisano_period_at_15

namespace Problems.Minif2f.mathd_numbertheory_405

-- Reduce to Pisano periodicity at residue 15 mod 16: t (16k+15) % 7 = 1.
-- Combinator: extract c % 16 = 15 from h₅, write c = 16*(c/16)+15, then apply.
theorem s9443 : ∀ (c : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1) (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₅ : c ≡ 15 [MOD 16]), t c % 7 = 1  := by
  intro c t h₀ h₁ h₂ h₅
  have h_period : ∀ k, t (16 * k + 15) % 7 = 1 :=
    pisano_period_at_15 t h₀ h₁ h₂
  have h_mod : c % 16 = 15 := by
    have := h₅
    unfold Nat.ModEq at this
    omega
  have h_decompose : c = 16 * (c / 16) + 15 := by
    have hd := Nat.div_add_mod c 16
    omega
  rw [h_decompose]
  exact h_period (c / 16)

end Problems.Minif2f.mathd_numbertheory_405
