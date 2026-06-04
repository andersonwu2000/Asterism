import Mathlib
namespace Problems.Minif2f.mathd_algebra_140

-- ab_eq_twelve: evaluate the polynomial identity at x=0,1,-1; adding x=1 and x=-1
-- specialisations cancels ac and 10b terms, giving 4ab=48 which nlinarith closes
theorem ab_eq_twelve : ∀ (a b c : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c)
    (h₁ : ∀ x, 24 * x ^ 2 - 19 * x - 35 = (a * x - 5) * (2 * (b * x) + c)), a * b = 12 := by
  intro a b c _ h₁
  have h0 := h₁ 0
  have h1 := h₁ 1
  have hn1 := h₁ (-1)
  ring_nf at h0 h1 hn1
  nlinarith [h0, h1, hn1]

end Problems.Minif2f.mathd_algebra_140
