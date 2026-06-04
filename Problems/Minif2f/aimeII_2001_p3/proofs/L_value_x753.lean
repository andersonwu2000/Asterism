-- Decompose via period-10: extract x(n+10) = x(n) for n ≥ 1 as a sub-goal,
-- then iterate by induction on k to reduce x 753 = x (3 + 10*75) = x 3 = 420.
import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs._strategy_s771

namespace Problems.Minif2f.aimeII_2001_p3

def value_x753 := @Problems.Minif2f.aimeII_2001_p3.s771

end Problems.Minif2f.aimeII_2001_p3
