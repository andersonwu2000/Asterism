import Mathlib
import Problems.Minif2f.mathd_algebra_131.Defs
import Problems.Minif2f.mathd_algebra_131.proofs.L_prod_eq
import Problems.Minif2f.mathd_algebra_131.proofs.L_sum_eq

namespace Problems.Minif2f.mathd_algebra_131

-- Vieta's: split into sum (a+b=7/2) and product (a*b=1) of roots.
-- Closer derives a≠1, b≠1 from Vieta (else b would have to equal both 5/2 and 1),
-- then field_simp + linarith reduces 1/(a-1)+1/(b-1)=-1 to a linear identity in a+b, ab.
theorem s9299 : ∀ (a b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = 2 * x ^ 2 - 7 * x + 2)
    (h₁ : f a = 0) (h₂ : f b = 0) (h₃ : a ≠ b),
    1 / (a - 1) + 1 / (b - 1) = -1 := by
  intro a b f h₀ h₁ h₂ h₃
  have h_sum : a + b = 7 / 2 := sum_eq a b f h₀ h₁ h₂ h₃
  have h_prod : a * b = 1 := prod_eq a b f h₀ h₁ h₂ h₃
  have ha1 : a - 1 ≠ 0 := by
    intro hEq
    have ha : a = 1 := by linarith
    rw [ha] at h_prod h_sum
    have hb1 : b = 1 := by linarith
    have hb2 : b = 5 / 2 := by linarith
    linarith
  have hb1 : b - 1 ≠ 0 := by
    intro hEq
    have hb : b = 1 := by linarith
    rw [hb] at h_prod h_sum
    have ha1 : a = 1 := by linarith
    have ha2 : a = 5 / 2 := by linarith
    linarith
  field_simp
  linarith [h_sum, h_prod, mul_comm a b]

end Problems.Minif2f.mathd_algebra_131
