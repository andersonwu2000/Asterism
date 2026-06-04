import Mathlib
import Problems.Minif2f.mathd_algebra_482.Defs
import Problems.Minif2f.mathd_algebra_482.proofs.L_k_eq_root_prod
import Problems.Minif2f.mathd_algebra_482.proofs.L_prime_pair_5_7

namespace Problems.Minif2f.mathd_algebra_482

-- Decompose via Vieta: derive `k = m * n` (product of roots) and the prime-pair
-- enumeration `(m=5 ∧ n=7) ∨ (m=7 ∧ n=5)`, then case-split and `norm_num`.
theorem s9256 : ∀ (m n : ℕ) (k : ℝ) (f : ℝ → ℝ) (h₀ : Nat.Prime m) (h₁ : Nat.Prime n) (h₂ : ∀ x, f x = x ^ 2 - 12 * x + k) (h₃ : f m = 0) (h₄ : f n = 0) (h₅ : m ≠ n), k = 35  := by
  intro m n k f h₀ h₁ h₂ h₃ h₄ h₅
  have h_prod : k = (m : ℝ) * n := k_eq_root_prod m n k f h₀ h₁ h₂ h₃ h₄ h₅
  have h_pair : (m = 5 ∧ n = 7) ∨ (m = 7 ∧ n = 5) :=
    prime_pair_5_7 m n k f h₀ h₁ h₂ h₃ h₄ h₅
  rcases h_pair with ⟨hm, hn⟩ | ⟨hm, hn⟩ <;>
    (rw [h_prod, hm, hn]; push_cast; norm_num)

end Problems.Minif2f.mathd_algebra_482
