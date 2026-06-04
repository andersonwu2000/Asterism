-- Decompose `x = √2 ∨ 3 < x` for positive roots of `x^(2^√2) = √2^(2^x)` via
-- two non-existence sub-goals on the complementary intervals:
--   (a) the equation has no root in (0, √2);
--   (b) the equation has no root in (√2, 3].
-- Trichotomy on `x` vs `√2` and a case-split on `x ≤ 3` vs `3 < x` then forces
-- `x = √2 ∨ 3 < x`. Each sub-goal is strictly simpler than the parent: it
-- drops the disjunction in the conclusion and adds an extra interval bound on x.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9708

namespace Problems.Minif2f.amc12b_2021_p21

def root_sqrt2_or_gt_three := @Problems.Minif2f.amc12b_2021_p21.s9708

end Problems.Minif2f.amc12b_2021_p21
