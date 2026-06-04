import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- frac_b_upper: mediant inequality b/(a+b+c) < (b+d)/(a+b+c+d)
-- Cross-multiply via div_lt_div_iff₀; residual b*(a+b+c+d) < (b+d)*(a+b+c)
-- reduces to d*(a+c) > 0, closed by nlinarith.
set_option linter.unusedVariables false in
set_option linter.style.longLine false in
theorem frac_b_upper : ∀ (a b c d s : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d) (h₁ : s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)), b / (a + b + c) < (b + d) / (a + b + c + d) := by
  intro a b c d s ⟨ha, hb, hc, hd⟩ _
  have habc : (0 : ℝ) < a + b + c := by linarith
  have habcd : (0 : ℝ) < a + b + c + d := by linarith
  rw [div_lt_div_iff₀ habc habcd]
  nlinarith

end Problems.Minif2f.imo_1974_p5
