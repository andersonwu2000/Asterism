-- Split product modulo 19 factor-wise via `Int.mul_emod`.
-- Sub-goals: (x+1)^2 % 19 = 6 from x % 19 = 4 (since 5^2 = 25 ≡ 6),
-- and (y+5)^3 % 19 = 18 from y % 19 = 7 (since 12^3 = 1728 ≡ -1 ≡ 18);
-- then 6 * 18 % 19 = 108 % 19 = 13 by `decide`.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_412.Defs
import Problems.Minif2f.mathd_numbertheory_412.proofs._strategy_s9310

namespace Problems.Minif2f.mathd_numbertheory_412

def main := @Problems.Minif2f.mathd_numbertheory_412.s9310

end Problems.Minif2f.mathd_numbertheory_412
