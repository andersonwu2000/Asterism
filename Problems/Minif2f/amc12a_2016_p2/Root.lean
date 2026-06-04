-- Split into 2 sub-goals: (A) algebraic combine `10^x * 100^(2x) = 10^(5x)`,
-- (B) injectivity finisher `10^(5x) = 1000^5 → x = 3`. Combinator: rewrite h₀
-- via (A), then apply (B). Each piece is strictly simpler: (A) is pure rpow
-- arithmetic with `100 = 10^2`, (B) is `1000^5 = 10^15` + rpow injectivity at base 10.
import Mathlib
import Problems.Minif2f.amc12a_2016_p2.Defs
import Problems.Minif2f.amc12a_2016_p2.proofs._strategy_s9366

namespace Problems.Minif2f.amc12a_2016_p2

def main := @Problems.Minif2f.amc12a_2016_p2.s9366

end Problems.Minif2f.amc12a_2016_p2
