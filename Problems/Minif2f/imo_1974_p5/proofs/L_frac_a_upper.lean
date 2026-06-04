import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- frac_a_upper: mediant inequality a/(a+b+d) < (a+c)/(a+b+c+d); cross-multiply and
-- reduce to 0 < c*(b+d) via nlinarith on positivity hypotheses.
theorem frac_a_upper :
    ∀ (a b c d s : ℝ),
    (0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d) →
    (s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)) →
    a / (a + b + d) < (a + c) / (a + b + c + d) := by
  intro a b c d _s h₀ _h₁
  obtain ⟨ha, hb, hc, hd⟩ := h₀
  have hab : 0 < a + b + d := by linarith
  have habcd : 0 < a + b + c + d := by linarith
  rw [div_lt_div_iff₀ hab habcd]
  nlinarith

end Problems.Minif2f.imo_1974_p5
