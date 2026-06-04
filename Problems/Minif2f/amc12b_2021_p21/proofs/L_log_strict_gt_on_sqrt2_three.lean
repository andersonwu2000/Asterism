-- Concavity-chord decomposition. Let g(y) := 2^√2 · log y − 2^y · log √2.
-- Then g(√2)=0 (absorbed), g is strictly concave on (0,∞) (g'' < 0), and g(3)>0.
-- By concavity, (3−√2)·g(y) ≥ (y−√2)·g(3) for y ∈ [√2, 3] (chord lower bound).
-- For √2 < y ≤ 3: (y−√2) > 0 and g(3) > 0, so (3−√2)·g(y) > 0, hence g(y) > 0.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9789

namespace Problems.Minif2f.amc12b_2021_p21

def log_strict_gt_on_sqrt2_three := @Problems.Minif2f.amc12b_2021_p21.s9789

end Problems.Minif2f.amc12b_2021_p21
