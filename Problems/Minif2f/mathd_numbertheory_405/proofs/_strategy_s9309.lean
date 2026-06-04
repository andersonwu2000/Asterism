import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_pisano_mod_10
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_pisano_mod_15
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_t_pisano_mod_5

namespace Problems.Minif2f.mathd_numbertheory_405

-- Split by variable a/b/c into three independent Pisano-residue lemmas:
-- `t a % 7 = 5`, `t b % 7 = 6`, `t c % 7 = 1`, since the Fibonacci-like
-- sequence `t` has Pisano period 16 mod 7, and 5+6+1 = 12 ≡ 5 (mod 7).
-- Combinator: omega on the three modular residues.
theorem s9309 : ∀ (a b c : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1) (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₃ : a ≡ 5 [MOD 16]) (h₄ : b ≡ 10 [MOD 16]) (h₅ : c ≡ 15 [MOD 16]), (t a + t b + t c) % 7 = 5  := by
  intro a b c t h₀ h₁ h₂ h₃ h₄ h₅
  have h_ta := t_pisano_mod_5 a t h₀ h₁ h₂ h₃
  have h_tb := t_pisano_mod_10 b t h₀ h₁ h₂ h₄
  have h_tc := t_pisano_mod_15 c t h₀ h₁ h₂ h₅
  omega
