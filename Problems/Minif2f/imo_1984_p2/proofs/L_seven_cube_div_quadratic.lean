-- Reduce (a+b)^7 - a^7 - b^7 = 7·a·b·(a+b)·(a^2+ab+b^2)^2 via algebraic identity,
-- then cancel the prime-7 factors carried by a, b, a+b to get 7^3 ∣ a^2+ab+b^2.
import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs._strategy_s9425

namespace Problems.Minif2f.imo_1984_p2

def seven_cube_div_quadratic := @Problems.Minif2f.imo_1984_p2.s9425

end Problems.Minif2f.imo_1984_p2
