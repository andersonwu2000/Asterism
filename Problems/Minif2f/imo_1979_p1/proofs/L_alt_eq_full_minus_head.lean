-- Bridge alternating sum to (sum_all − sum_head) via the even-indexed half.
-- h_alt rewrites the alternating sum as full minus 2·(sum of 1/(2j) for j∈[1,659]);
-- h_double collapses 2·∑ 1/(2j) to ∑ 1/j. Combine with linarith.
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9649

namespace Problems.Minif2f.imo_1979_p1

def alt_eq_full_minus_head := @Problems.Minif2f.imo_1979_p1.s9649

end Problems.Minif2f.imo_1979_p1
