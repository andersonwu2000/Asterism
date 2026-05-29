-- Split the conjunction into its two independent conjuncts.
-- h_disj: distinct head-letters give disjoint word-sets (head? is functional).
-- h_cover: non-empty words are exactly those with some head-letter (head? = some p).
-- Each conjunct stands alone and is strictly simpler than the pair; combine with And.intro.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11387

namespace Problems.Geometry.banach_tarski

def freegroup_starts_disjoint_cover := @Problems.Geometry.banach_tarski.s11387

end Problems.Geometry.banach_tarski
