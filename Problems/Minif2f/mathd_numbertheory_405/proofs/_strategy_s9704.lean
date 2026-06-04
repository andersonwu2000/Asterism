import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_pair_inv_period_16_mod_7

namespace Problems.Minif2f.mathd_numbertheory_405

-- Pair-invariant decomposition: strengthen periodicity to the pair
-- `(t(n+16) % 7 = t n % 7) ∧ (t(n+17) % 7 = t(n+1) % 7)`, which admits
-- direct `Nat.rec` induction because the recurrence at `n+18` lifts the
-- pair forward by one step. Combinator: project the first component.
theorem s9704
    (a : ℕ) (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) (h₃ : a ≡ 5 [MOD 16]) :
    ∀ n, t (n + 16) % 7 = t n % 7  := by
  have h_pair := pair_inv_period_16_mod_7 a t h₀ h₁ h₂ h₃
  intro n
  exact (h_pair n).1

end Problems.Minif2f.mathd_numbertheory_405
