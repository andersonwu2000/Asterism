-- Clear denominators on each bound separately, reducing to integer bounds on y.
-- `lt_98_of_lower_bound`: 8/15 < 112/(112+y) → y < 98 (cross-multiply).
-- `gt_96_of_upper_bound`: 112/(112+y) < 7/13 → 96 < y (cross-multiply).
-- Combined: 96 < y < 98 → y = 97 by `omega`.
import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs._strategy_s9474

namespace Problems.Minif2f.aime_1987_p8

def k_eq_97_from_bounds := @Problems.Minif2f.aime_1987_p8.s9474

end Problems.Minif2f.aime_1987_p8
