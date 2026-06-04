-- Reduce to a periodic-5 block invariant: for every k, the tuple
-- (t(5k+1), t(5k+2), t(5k+3), t(5k+4), t(5k+5)) equals (20, 21, 53/250, 103/26250, 101/525).
-- Specialize at k = 403 (since 5*403 + 5 = 2020) and project the 5th conjunct.
-- The block_invariant is structurally bigger (induction on k, base case = direct recurrence
-- chain t 3..t 5, step = same recurrence applied to the next block of five) so it goes to
-- Backward; the parent reduction is a mechanical obtain + simpa.
import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs
import Problems.Minif2f.aimeII_2020_p6.proofs._strategy_s9393

namespace Problems.Minif2f.aimeII_2020_p6

def t_2020_eq := @Problems.Minif2f.aimeII_2020_p6.s9393

end Problems.Minif2f.aimeII_2020_p6
