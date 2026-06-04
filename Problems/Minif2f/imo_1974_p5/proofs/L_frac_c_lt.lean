import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- frac_c_lt: c/(a+b+c+d) < c/(b+c+d) for positive reals via div_lt_div_iff₀
-- Rewrite with div_lt_div_iff₀ (both denominators positive by linarith), then
-- nlinarith closes c*(b+c+d) < c*(a+b+c+d) using c>0, a>0.
theorem frac_c_lt : ∀ (a b c d : ℝ), 0 < a → 0 < b → 0 < c → 0 < d →
    c / (a + b + c + d) < c / (b + c + d) := by
  intro a b c d ha hb hc hd
  rw [div_lt_div_iff₀ (by linarith) (by linarith)]
  nlinarith

end Problems.Minif2f.imo_1974_p5
