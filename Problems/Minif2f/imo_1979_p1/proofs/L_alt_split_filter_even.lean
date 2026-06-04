-- Bridge alternating sum to (full − 2·even-half) via two strictly simpler pieces:
-- `pointwise_sign_to_diff`: the ∀-quantified termwise identity
--   (-1)^(k+1)·(1/k) = 1/k − 2·(if Even k then 1/k else 0)
-- `sum_pointwise_to_filtered`: linearity-of-∑ + Finset.sum_filter to collapse
--   the indicator-weighted sum into a sum over the Even-filtered Icc.
-- Combine: rewrite the alternating sum termwise, then invoke the assembly.
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9750

namespace Problems.Minif2f.imo_1979_p1

def alt_split_filter_even := @Problems.Minif2f.imo_1979_p1.s9750

end Problems.Minif2f.imo_1979_p1
