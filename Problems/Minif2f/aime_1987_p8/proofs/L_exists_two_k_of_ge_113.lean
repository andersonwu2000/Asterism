-- Witnesses k1 = ⌊6n/7⌋ + 1 and k2 = ⌊6n/7⌋ + 2 (Nat division). Both are
-- distinct (omega), satisfy the integer bounds 6n < 7k ∧ 8k < 7n for n ≥ 113
-- (omega via length-of-real-interval (6n/7, 7n/8) = n/56 > 2), and the
-- single sub-goal converts those Nat inequalities to the real division
-- inequalities (cross-multiplication using n+k > 0).
import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs._strategy_s9334

namespace Problems.Minif2f.aime_1987_p8

def exists_two_k_of_ge_113 := @Problems.Minif2f.aime_1987_p8.s9334

end Problems.Minif2f.aime_1987_p8
