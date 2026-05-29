-- Uncountable-sphere escape: the union over n of the n+1-power fixed sets on the
-- radius-1/2 sphere is countable (fixed_union_countable: each finite ⇒ countable union),
-- so the uncountable sphere is not contained in it; pick c in the sphere outside the union.
-- That c has ‖c‖ = 1/2 ≤ 1/2, and any positive power fixing c would place c (= R^(m+1) c)
-- back into the union, contradicting the choice. The lone sub-goal is the countability fact.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11519

namespace Problems.Geometry.banach_tarski

def exists_not_fixed_in_uncountable_sphere := @Problems.Geometry.banach_tarski.s11519

end Problems.Geometry.banach_tarski
