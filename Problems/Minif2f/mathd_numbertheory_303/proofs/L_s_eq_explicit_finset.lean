-- Split the Finset equality into two membership directions and stitch via Finset.ext.
-- Sub-goal 1 (cond_implies_in_set): the predicate forces n ∈ {7,13,91}.
-- Sub-goal 2 (in_set_implies_cond): each of 7,13,91 satisfies the predicate (decidable).
-- Both directions are strictly simpler than the original Finset equality.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs
import Problems.Minif2f.mathd_numbertheory_303.proofs._strategy_s9347

namespace Problems.Minif2f.mathd_numbertheory_303

def s_eq_explicit_finset := @Problems.Minif2f.mathd_numbertheory_303.s9347

end Problems.Minif2f.mathd_numbertheory_303
