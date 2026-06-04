-- Telescoping sum: induct on n. Base n=0 reduces by `simp`; step uses
-- `Finset.sum_range_succ` + ih, then `push_cast`/`field_simp`/`ring`
-- to close `n/(n+1) + 1/((n+1)(n+2)) = (n+1)/(n+2)`.
import Mathlib
import Problems.Minif2f.induction_sum_1oktkp1.Defs
import Problems.Minif2f.induction_sum_1oktkp1.proofs._strategy_s628

namespace Problems.Minif2f.induction_sum_1oktkp1

def main := @Problems.Minif2f.induction_sum_1oktkp1.s628

end Problems.Minif2f.induction_sum_1oktkp1
