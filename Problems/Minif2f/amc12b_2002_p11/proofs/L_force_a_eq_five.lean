-- Decompose into (1) parity argument forcing b = 2, and (2) prime-triplet
-- argument forcing a = 5 once b = 2 is known.
-- After substituting b = 2, the original parameters Nat.Prime (a + b) and
-- Nat.Prime (a - b) become Nat.Prime (a + 2) and Nat.Prime (a - 2), which
-- exactly match the hypotheses of the second sub-goal.
import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs._strategy_s9326

namespace Problems.Minif2f.amc12b_2002_p11

def force_a_eq_five := @Problems.Minif2f.amc12b_2002_p11.s9326

end Problems.Minif2f.amc12b_2002_p11
