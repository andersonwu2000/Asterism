-- Reduce to the closed-form value of a at n=2019.
-- Reciprocal b n = 1/a n satisfies b(n+2) = 2 b(n+1) - b n (arithmetic progression),
-- giving a n = 3/(4n-1); at n=2019 we get a 2019 = 3/8075,
-- and the den+num arithmetic on 3/8075 closes the goal.
import Mathlib
import Problems.Minif2f.amc12a_2019_p9.Defs
import Problems.Minif2f.amc12a_2019_p9.proofs._strategy_s589

namespace Problems.Minif2f.amc12a_2019_p9

def main := @Problems.Minif2f.amc12a_2019_p9.s589

end Problems.Minif2f.amc12a_2019_p9
