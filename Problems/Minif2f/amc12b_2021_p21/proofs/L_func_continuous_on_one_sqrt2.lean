-- Split into f1(t) = 2^t * log(√2) and f2(t) = 2^√2 * log t, apply ContinuousOn.sub.
-- f1 is rpow-of-constant-base times a constant. f2 is a constant times Real.log,
-- which is continuous on the interval since t ≥ 1 > 0.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9827

namespace Problems.Minif2f.amc12b_2021_p21

def func_continuous_on_one_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9827

end Problems.Minif2f.amc12b_2021_p21
