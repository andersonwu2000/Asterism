import Mathlib
namespace Problems.Minif2f.mathd_algebra_140

-- c_eq_seven: evaluate polynomial identity at x=0 to extract -35 = -5*c, then linarith gives c=7
theorem c_eq_seven : ∀ (a b c : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c)
    (h₁ : ∀ x, 24 * x ^ 2 - 19 * x - 35 = (a * x - 5) * (2 * (b * x) + c)), c = 7 := by
  intro a b c h₀ h₁
  have h0 := h₁ 0
  simp at h0
  linarith

end Problems.Minif2f.mathd_algebra_140
