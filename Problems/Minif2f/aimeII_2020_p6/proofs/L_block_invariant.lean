-- Induct on k. Base case k=0 is a concrete recurrence chain unfolding
-- t 3, t 4, t 5 from h₀, h₁ via h₂; step uses the recurrence at indices
-- 5k+6 and 5k+7 (depending on t(5k+4), t(5k+5)) which collapse to 20, 21,
-- after which 5k+8, 5k+9, 5k+10 follow mechanically — so step is a fixed
-- 5-link computation independent of k.
import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs
import Problems.Minif2f.aimeII_2020_p6.proofs._strategy_s9475

namespace Problems.Minif2f.aimeII_2020_p6

def block_invariant := @Problems.Minif2f.aimeII_2020_p6.s9475

end Problems.Minif2f.aimeII_2020_p6
