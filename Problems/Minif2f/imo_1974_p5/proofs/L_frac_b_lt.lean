import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- frac_b_lt: div_lt_div_iff₀ reduces to b*(a+b+c) < b*(a+b+c+d), closed by nlinarith
-- Same numerator b > 0; denominator a+b+c+d > a+b+c since d > 0.
theorem frac_b_lt : ∀ (a b c d : ℝ), 0 < a → 0 < b → 0 < c → 0 < d →
    b / (a + b + c + d) < b / (a + b + c) := by
  intro a b c d ha hb hc hd
  rw [div_lt_div_iff₀ (by linarith) (by linarith)]
  nlinarith

end Problems.Minif2f.imo_1974_p5
