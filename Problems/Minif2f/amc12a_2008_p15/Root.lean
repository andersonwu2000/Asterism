-- Decompose `(k^2 + 2^k) % 10 = 6` for `k = 2008^2 + 2^2008` into 3 facts about k
-- (k % 10 = 0, k % 4 = 0, 4 ≤ k) plus an abstract arithmetic combinator.
-- `native_decide` is dead — `2^2008` blows recursion depth (lesson learned).
-- The combinator drops k/h₀ binders intentionally: it is a truly abstract helper
-- on any natural m satisfying the three modular/size hypotheses.
import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs._strategy_s782

namespace Problems.Minif2f.amc12a_2008_p15

def main := @Problems.Minif2f.amc12a_2008_p15.s782

end Problems.Minif2f.amc12a_2008_p15
