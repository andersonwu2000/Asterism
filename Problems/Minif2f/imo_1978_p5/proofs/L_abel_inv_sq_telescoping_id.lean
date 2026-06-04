-- Abel summation by parts against weights 1/k². Split the identity in two:
--   (1) `sum_diff_eq_sum_of_diff` — pure sum_sub_distrib: LHS difference of two
--       sums equals the single sum ∑ ((a k - k)/k²).
--   (2) `abel_summation_inv_sq` — the Abel telescoping itself: rewrite
--       ∑ b(k)/k² (b(k) := a(k) - k) as the weight-difference combination plus
--       the boundary 1/(n+1)² term. Provable by induction on n.
-- Combinator: linarith chains h_sub + h_abel to produce the parent equation.
import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs._strategy_s9688

namespace Problems.Minif2f.imo_1978_p5

def abel_inv_sq_telescoping_id := @Problems.Minif2f.imo_1978_p5.s9688

end Problems.Minif2f.imo_1978_p5
