-- Direct proof: bound b ≤ 4 via nlinarith from h₁ (since 3b² grows fast),
-- then interval_cases on b discharges all five cases (0 killed by h₀,
-- 1/2/3 by h₁ arithmetic, 4 by rfl) via omega.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_48.Defs
import Problems.Minif2f.mathd_numbertheory_48.proofs._strategy_s9312

namespace Problems.Minif2f.mathd_numbertheory_48

def main := @Problems.Minif2f.mathd_numbertheory_48.s9312

end Problems.Minif2f.mathd_numbertheory_48
