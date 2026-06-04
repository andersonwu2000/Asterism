-- Direct proof: rearrange to `0 ≤ 36z² - 36az + 9a² = (6z - 3a)²`.
-- `nlinarith` closes the goal given `sq_nonneg (6*z - 3*a)` as a hint —
-- the square expansion supplies exactly the cross-term cancellation.
import Mathlib
import Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq.Defs
import Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq.proofs._strategy_s559

namespace Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq

def main := @Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq.s559

end Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq
