-- Reduce `y^(2^√2) < √2^(2^y)` to its log-linear form
-- `(2^√2) · log y < (2^y) · log √2`. Both sides of the original strict
-- inequality are positive (rpow of positive bases), so `Real.log_lt_log_iff`
-- and `Real.log_rpow` give an equivalence; the log form removes nested rpow
-- and exposes the analytical core (g(y) := (2^y)·log√2 − (2^√2)·log y, with
-- g(1) = log 2 > 0 and g(√2) = 0, decreasing on [1, √2)) for the sub-goal.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9788

namespace Problems.Minif2f.amc12b_2021_p21

def strict_lt_on_one_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9788

end Problems.Minif2f.amc12b_2021_p21
