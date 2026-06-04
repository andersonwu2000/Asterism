import Mathlib
namespace Problems.Minif2f.mathd_algebra_482

-- k_eq_root_prod: Vieta product formula — k equals product of roots m*n
-- From f(m)=0 and f(n)=0 derive (m-n)(m+n-12)=0; since m≠n get m+n=12; then k=m*n by ring.
theorem k_eq_root_prod : ∀ (m n : ℕ) (k : ℝ) (f : ℝ → ℝ) (_h₀ : Nat.Prime m)
    (_h₁ : Nat.Prime n) (h₂ : ∀ x, f x = x ^ 2 - 12 * x + k) (h₃ : f m = 0)
    (h₄ : f n = 0) (h₅ : m ≠ n), k = (m : ℝ) * n := by
  intro m n k f _h₀ _h₁ h₂ h₃ h₄ h₅
  have hm : (↑m : ℝ) ^ 2 - 12 * ↑m + k = 0 := by
    have hfm := h₂ (↑m : ℝ); rw [← hfm]; exact h₃
  have hn : (↑n : ℝ) ^ 2 - 12 * ↑n + k = 0 := by
    have hfn := h₂ (↑n : ℝ); rw [← hfn]; exact h₄
  have hmn_ne : (↑m : ℝ) ≠ ↑n := by exact_mod_cast h₅
  have key : ((↑m : ℝ) - ↑n) * ((↑m : ℝ) + ↑n - 12) = 0 := by
    linear_combination hm - hn
  rcases mul_eq_zero.mp key with h1 | h2
  · exact absurd (sub_eq_zero.mp h1) hmn_ne
  · linear_combination hm - (↑m : ℝ) * h2

end Problems.Minif2f.mathd_algebra_482
