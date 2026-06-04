import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.proofs.L_recursion_squared
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.proofs.L_seq_ge_two

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

-- Reduce sqrt-equation to two pure arithmetic claims:
--   (1) recursion_squared: a (n+1) = (a n - 2)^2 (from the product recurrence).
--   (2) seq_ge_two       : a n ≥ 2 (so a n - 2 ≥ 0, removing the sqrt branch).
-- Combinator: rewrite a (n+1) by (1), apply Real.sqrt_sq to the nonneg base from (2), ring.
theorem s9383 : ∀ (a : ℕ → ℝ) (h₀ : a 0 = 1) (h₁ : ∀ n, a (n + 1) = (∏ k ∈ Finset.range (n + 1), a k) + 4), ∀ n ≥ 1, a n - Real.sqrt (a (n + 1)) = 2  := by
  intro a h₀ h₁ n hn
  have h_sq : a (n + 1) = (a n - 2) ^ 2 := recursion_squared a h₀ h₁ n hn
  have h_ge : a n ≥ 2 := seq_ge_two a h₀ h₁ n hn
  rw [h_sq, Real.sqrt_sq (by linarith : (0:ℝ) ≤ a n - 2)]
  ring


end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

