import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_n_eq_864

namespace Problems.Minif2f.mathd_numbertheory_709

-- Decompose: the only n with 0<n, τ(2n)=28, τ(3n)=30 is n = 864.
-- Sub-goal `n_eq_864` does the integer/divisor-count work; we then substitute
-- and close τ(6·864)=35 by `native_decide` (kernel decision per LESSONS).
theorem s9316 : ∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28) (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), Finset.card (Nat.divisors (6 * n)) = 35  := by
  intro n h₀ h₁ h₂
  have hn : n = 864 := n_eq_864 n h₀ h₁ h₂
  subst hn
  native_decide

end Problems.Minif2f.mathd_numbertheory_709
