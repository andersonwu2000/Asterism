-- Bridge `2^√2 · log y < 2^y · log √2` on [1, √2) to a single monotonicity claim.
-- Set g(t) := 2^t · log √2 − 2^√2 · log t.  Then g(√2) = 0 (algebraic cancellation),
-- and g is strictly antitone on [1, √2] (g'(t) = 2^t · (log 2)(log √2) − 2^√2/t
-- stays negative throughout the interval, since the −2^√2/t term dominates).  For
-- y < √2 in [1, √2): StrictAntiOn gives g(√2) < g(y); after expanding the lambda,
-- the LHS is `2^√2 · log √2 − 2^√2 · log √2 = 0`, so linarith closes against the
-- parent inequality.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9804

namespace Problems.Minif2f.amc12b_2021_p21

def log_strict_lt_on_one_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9804

end Problems.Minif2f.amc12b_2021_p21
