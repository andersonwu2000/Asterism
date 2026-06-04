-- Two-step reduction via the identity
--   (a+b)^7 - a^7 - b^7 = 7·a·b·(a+b)·(a^2 + a·b + b^2)^2.
-- (1) seven_cube_div_quadratic: from 7^7 ∣ … and the three non-divisibilities,
--     cancel the prime factors carried by 7·a·b·(a+b) and conclude 7^3 ∣ a^2 + a·b + b^2.
-- (2) bound_from_div: from 7^3 = 343 ∣ a^2 + a·b + b^2 plus positivity, enumerate
--     the finitely many small candidate values of a+b ≤ 18 to rule them out.
import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs._strategy_s9292

namespace Problems.Minif2f.imo_1984_p2

def main := @Problems.Minif2f.imo_1984_p2.s9292

end Problems.Minif2f.imo_1984_p2
