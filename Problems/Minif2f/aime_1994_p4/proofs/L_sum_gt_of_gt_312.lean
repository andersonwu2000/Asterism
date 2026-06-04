-- Trichotomy upper branch: for m > 312 the floor-log sum strictly exceeds 1994.
-- Two sub-goals: (1) a numerical anchor at m = 313 showing the sum is already
-- > 1994 there, and (2) monotonicity of the partial sum in m (each floor term
-- is non-negative for k ≥ 1), so growing m past 313 only adds. `linarith`
-- chains the two.
import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs
import Problems.Minif2f.aime_1994_p4.proofs._strategy_s9359

namespace Problems.Minif2f.aime_1994_p4

def sum_gt_of_gt_312 := @Problems.Minif2f.aime_1994_p4.s9359

end Problems.Minif2f.aime_1994_p4
