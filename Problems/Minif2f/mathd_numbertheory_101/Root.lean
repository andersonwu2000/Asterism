-- Pure ℕ decidable arithmetic: 17 * 18 = 306 = 76 * 4 + 2, so 306 % 4 = 2.
-- `decide` reduces `17 * 18 % 4 = 2` to `Nat.beq` and discharges by reflection.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_101.Defs
import Problems.Minif2f.mathd_numbertheory_101.proofs._strategy_s517

namespace Problems.Minif2f.mathd_numbertheory_101

def main := @Problems.Minif2f.mathd_numbertheory_101.s517

end Problems.Minif2f.mathd_numbertheory_101
