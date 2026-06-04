import Mathlib
namespace Problems.Minif2f.imo_1988_p6

-- vieta_a_le_kb: prove a ≤ k*b via zify + nlinarith on the Vieta identity
-- Cast to ℤ then let nlinarith combine sq_nonneg (a - k*b) with the identity to close.
theorem vieta_a_le_kb : ∀ (a b k : ℕ), 0 < a → 0 < b → b < a →
    a^2 + b^2 = (a*b + 1) * k → a ≤ k * b := by
  intro a b k ha hb hba heq
  zify at *
  nlinarith [sq_nonneg ((a : ℤ) - k * b), sq_nonneg ((a : ℤ) - b), sq_nonneg ((b : ℤ))]

end Problems.Minif2f.imo_1988_p6
