-- Reduce `√2^(2^y) < y^(2^√2)` to its log-linear form
-- `(2^y) · log(√2) < (2^√2) · log y`. Both sides of the original strict
-- inequality are positive (rpow of positive bases), so `Real.log_lt_log_iff`
-- and `Real.log_rpow` give an equivalence; the log form removes nested rpow
-- and exposes the analytical core (concave g(y) := (2^√2)·log y − 2^y·log√2
-- with g(√2)=0 and g(3)>0) for the sub-goal to handle.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9771

namespace Problems.Minif2f.amc12b_2021_p21

def strict_gt_on_sqrt2_three := @Problems.Minif2f.amc12b_2021_p21.s9771

end Problems.Minif2f.amc12b_2021_p21
