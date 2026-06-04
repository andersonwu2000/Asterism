import Mathlib
import Problems.Minif2f.mathd_algebra_482.Defs
import Problems.Minif2f.mathd_algebra_482.proofs.L_prime_pair_sum_twelve
import Problems.Minif2f.mathd_algebra_482.proofs.L_sum_roots_eq_twelve

namespace Problems.Minif2f.mathd_algebra_482

-- Vieta + prime enumeration: from f(m)=f(n)=0 and m ≠ n derive m+n=12, then
-- enumerate prime pairs summing to 12 to get the disjunction (5,7) ∨ (7,5).
theorem s9420 : ∀ (m n : ℕ) (k : ℝ) (f : ℝ → ℝ) (h₀ : Nat.Prime m) (h₁ : Nat.Prime n) (h₂ : ∀ x, f x = x ^ 2 - 12 * x + k) (h₃ : f m = 0) (h₄ : f n = 0) (h₅ : m ≠ n), (m = 5 ∧ n = 7) ∨ (m = 7 ∧ n = 5)  := by
  intro m n k f h₀ h₁ h₂ h₃ h₄ h₅
  have h_sum := sum_roots_eq_twelve m n k f h₀ h₁ h₂ h₃ h₄ h₅
  have h_pair := prime_pair_sum_twelve m n k f h₀ h₁ h₂ h₃ h₄ h₅ h_sum
  exact h_pair

end Problems.Minif2f.mathd_algebra_482
