-- Direct: on `Metric.ball a R` the glued function equals `g` (uses `h_diff_eq`
-- off `a` and matches by definition at `a`), so it inherits differentiability
-- at `a` from `hg_an` via `Filter.EventuallyEq.differentiableAt_iff`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10565

namespace Problems.residue_thm

def glued_qmp_diff_at_pole := @Problems.residue_thm.s10565

end Problems.residue_thm
