-- Direct decision procedure: `omega` discharges linear arithmetic over ℕ with mod.
-- Given `n % 7 = 3`, we have `2 * n + 1 ≡ 2 * 3 + 1 = 7 ≡ 0 (mod 7)`; omega handles
-- the mod-7 case-split and closes the goal without sub-goals.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_370.Defs
import Problems.Minif2f.mathd_numbertheory_370.proofs._strategy_s725

namespace Problems.Minif2f.mathd_numbertheory_370

def main := @Problems.Minif2f.mathd_numbertheory_370.s725

end Problems.Minif2f.mathd_numbertheory_370
