-- Construct the witness `(p', q', r') = (b, r, a)`: new line through `b, r`
-- with `a` as off-line point. Three sub-claims:
-- (1) `b ≠ r` — `b` is on line(p,q) (param `t_b`), `r` is off (`¬ Collinear p q r`).
-- (2) `¬ Collinear b r a` — `a, b` are distinct points on line(p,q) (`t_a ≠ t_b`),
--     `r` is off, so `a` is not on line(b,r).
-- (3) Strict ratio inequality. Algebraic identities: new numerator factors as
--     `(t_b - t_a)^2 * OldNum`; new denominator `(r-b).1² + (r-b).2²` expands to
--     `OldNum/|q-p|² + (t_b - t_f)² · |q-p|²` using the foot-of-perpendicular
--     formula for `t_f`. The same-side + ordered hypotheses give
--     `(t_b - t_a)² ≤ (t_b - t_f)²`, and `OldNum > 0` (from `¬ Collinear p q r`)
--     supplies the strict gap.
import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs._strategy_s10216

namespace Problems.sylvester_gallai

def kelly_smaller_two_same_side_ordered := @Problems.sylvester_gallai.s10216

end Problems.sylvester_gallai
