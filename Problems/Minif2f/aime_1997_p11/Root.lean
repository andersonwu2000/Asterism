-- Reduce to closed form x = 1 + √2, then evaluate the floor.
-- (1) x_eq_one_plus_sqrt_two: trig telescoping gives x = 1 + √2.
-- (2) floor_hundred_one_plus_sqrt_two: arithmetic ⌊100·(1+√2)⌋ = 241.
import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs
import Problems.Minif2f.aime_1997_p11.proofs._strategy_s9479

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

def main := @Problems.Minif2f.aime_1997_p11.s9479

end Problems.Minif2f.aime_1997_p11
