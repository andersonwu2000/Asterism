-- Split f(x) = x^(2^√2) - √2^(2^x) into its two continuous parts and apply ContinuousOn.sub.
-- h1 handles continuity of x ↦ x^(2^√2) on [2,4] (positive base, constant exponent).
-- h2 handles continuity of x ↦ √2^(2^x) on [2,4] (positive constant base, continuous exponent).
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9718

namespace Problems.Minif2f.amc12b_2021_p21

def func_continuous_on := @Problems.Minif2f.amc12b_2021_p21.s9718

end Problems.Minif2f.amc12b_2021_p21
