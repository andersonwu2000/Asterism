-- Direct chord inequality from concavity: parameterize z = (1-t)·a + t·b with t = (z-a)/(b-a),
-- apply ConcaveOn.2 at a,b with weights (1-t), t; f(a)=0 collapses the LHS to t·f(b) ≤ f(z),
-- then clear denominator (b-a > 0).
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9821

namespace Problems.Minif2f.amc12b_2021_p21

def chord_zero_left_endpoint := @Problems.Minif2f.amc12b_2021_p21.s9821

end Problems.Minif2f.amc12b_2021_p21
