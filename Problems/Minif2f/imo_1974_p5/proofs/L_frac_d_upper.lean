import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- frac_d_upper: mediant inequality d/(a+c+d) < (b+d)/(a+b+c+d); cross-multiply and
-- reduce to 0 < b*(a+c) via nlinarith on positivity hypotheses.
theorem frac_d_upper :
    ∀ (a b c d s : ℝ) (_ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d)
    (_ : s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)),
    d / (a + c + d) < (b + d) / (a + b + c + d) := by
  intro a b c d _s ⟨ha, hb, hc, hd⟩ _
  have hacd : 0 < a + c + d := by linarith
  have habcd : 0 < a + b + c + d := by linarith
  rw [div_lt_div_iff₀ hacd habcd]
  nlinarith

end Problems.Minif2f.imo_1974_p5
