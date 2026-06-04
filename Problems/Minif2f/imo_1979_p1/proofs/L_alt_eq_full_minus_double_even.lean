-- Bridge alternating sum to (full − 2·even-half) by splitting the sign and reindexing.
-- h_alt_split: rewrite ∑ (-1)^(k+1)/k as ∑ 1/k − 2·∑_{Even k} 1/k via term-wise sign manipulation.
-- h_filter_reindex: identify the even-filtered sum with the j ↦ 2j reindexing onto [1,659].
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9689

namespace Problems.Minif2f.imo_1979_p1

def alt_eq_full_minus_double_even := @Problems.Minif2f.imo_1979_p1.s9689

end Problems.Minif2f.imo_1979_p1
