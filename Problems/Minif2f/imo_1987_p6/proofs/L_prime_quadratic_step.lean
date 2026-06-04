-- Case-split on whether `i ≤ ⌊√(p/3)⌋`.
-- • Small case: direct from `hk` (the given primality hypothesis).
-- • Large case: dispatched to `prime_quadratic_step_hard`, which receives
--   the extra premise `⌊√(p/3)⌋ < i` and is strictly simpler than the
--   parent (the trivial half of the case-split is discharged here).
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9656

namespace Problems.Minif2f.imo_1987_p6

def prime_quadratic_step := @Problems.Minif2f.imo_1987_p6.s9656

end Problems.Minif2f.imo_1987_p6
