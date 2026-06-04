-- Decompose into (1) pure ℕ arithmetic bound `5b < a → a < 6b → 22 ≤ a*b`
-- and (2) algebraic identity `lcm m l / gcd m l = (m/gcd) * (l/gcd)`.
-- Parent body: cast ℝ inequalities `n/k < 6`, `5 < n/k` to `n < 6k`, `5k < n`;
-- set d=gcd, a=n/d, b=k/d; derive `5b < a` and `a < 6b` via `Nat.lt_of_mul_lt_mul_right`;
-- rewrite lcm/gcd by (2) and close by (1).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_530.Defs
import Problems.Minif2f.mathd_numbertheory_530.proofs._strategy_s9313

namespace Problems.Minif2f.mathd_numbertheory_530

def main := @Problems.Minif2f.mathd_numbertheory_530.s9313

end Problems.Minif2f.mathd_numbertheory_530
