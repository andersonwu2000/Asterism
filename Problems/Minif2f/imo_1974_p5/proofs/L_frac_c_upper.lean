import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- frac_c_upper: mediant inequality; cross-multiply reduces to a*(b+d) > 0
theorem frac_c_upper :
    ∀ (a b c d s : ℝ) (_ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d)
    (_ : s = a / (a + b + d) + b / (a + b + c) + c / (b + c + d) + d / (a + c + d)),
    c / (b + c + d) < (a + c) / (a + b + c + d) := by
  intro a b c d s ⟨ha, hb, hc, hd⟩ _
  have hbcd : 0 < b + c + d := by linarith
  have habcd : 0 < a + b + c + d := by linarith
  rw [div_lt_div_iff₀ hbcd habcd]
  nlinarith

end Problems.Minif2f.imo_1974_p5
