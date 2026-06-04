-- Abstract the goal to the combinatorial fact: any self-inverse map on {0,…,1986}
-- (g(g a) = a whenever a < 1987) has a fixed point — independent of f, hff. The
-- closer applies the sub-goal at g = fun a => f a % 1987, with hg from Nat.mod_lt
-- and hgg = hinv verbatim.
import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs._strategy_s9723

namespace Problems.Minif2f.imo_1987_p4

def odd_involution_fixed := @Problems.Minif2f.imo_1987_p4.s9723

end Problems.Minif2f.imo_1987_p4
