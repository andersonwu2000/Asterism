-- Direct: hypothesis `0 ≤ f x` is vacuous since `Real.sqrt _ ≥ 0`, so the LHS set is `univ`.
-- Then `h₂` makes `f` surjective, contradicting `f x = sqrt _ ≥ 0` at the value `-1`.
-- The sign hypothesis `0 < a` is unused — h₀, h₁, h₂ alone are inconsistent.
import Mathlib
import Problems.Minif2f.amc12a_2003_p25.Defs
import Problems.Minif2f.amc12a_2003_p25.proofs._strategy_s780

namespace Problems.Minif2f.amc12a_2003_p25

def a_pos_contra := @Problems.Minif2f.amc12a_2003_p25.s780

end Problems.Minif2f.amc12a_2003_p25
