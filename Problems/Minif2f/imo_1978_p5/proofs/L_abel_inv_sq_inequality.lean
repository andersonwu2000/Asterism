-- Abel summation by parts against weight 1/k² (decreasing in k).
-- (1) `abel_inv_sq_telescoping_id`: pure algebraic identity rewriting the
--     difference ∑ a k / k² - ∑ k / k² as a manifestly-nonneg combination —
--     each weight difference (1/j² - 1/(j+1)²) is multiplied by a prefix sum
--     of (a k - k), plus a boundary term 1/(n+1)² times the total.
-- (2) `abel_inv_sq_telescoping_nonneg`: the RHS of (1) is ≥ 0, using that
--     each prefix sum is ≥ 0 (hypothesis), and each weight-diff > 0.
-- Combinator: `linarith` from the equation + ≥ 0 bound.
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9645

namespace Problems.Minif2f.imo_1978_p5

def abel_inv_sq_inequality := @Problems.Minif2f.imo_1978_p5.s9645

end Problems.Minif2f.imo_1978_p5
