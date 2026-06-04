-- Leaf: brute-force search after bounding x, y ≤ 35.
-- From h₀ (x, y ≥ 1) and h₁ (xy + x + y = 71), `nlinarith` derives x ≤ 35 and y ≤ 35.
-- `interval_cases` enumerates the 35*35 = 1225 pairs; `omega` discharges each
-- via the linear/numerical hypotheses (h₁ linear, h₂ numerical once x,y are constants).
import Mathlib
import Problems.Minif2f.aime_1991_p1.Defs
import Problems.Minif2f.aime_1991_p1.proofs._strategy_s9358

namespace Problems.Minif2f.aime_1991_p1

def sum_value := @Problems.Minif2f.aime_1991_p1.s9358

end Problems.Minif2f.aime_1991_p1
