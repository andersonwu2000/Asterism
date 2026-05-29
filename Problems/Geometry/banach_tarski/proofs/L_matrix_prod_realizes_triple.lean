-- Split off the per-letter matrix action as the single sub-goal `genmat_action_embed`
-- (each generator matrix on an embedded triple `![p√2,q,r√2]` realizes one `step`
-- recursion — no word, no induction). The combinator is a plain list induction folding
-- that bridge over `toWord w` (inlined rather than citing the proved general lemma
-- `s11395`/`matrix_prod_mulvec_realizes_foldr`, whose module is not auto-imported into a
-- strategy file unless it is a registered sub-goal); `hfold` then rewrites foldr to (p,q,r).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11399

namespace Problems.Geometry.banach_tarski

def matrix_prod_realizes_triple := @Problems.Geometry.banach_tarski.s11399

end Problems.Geometry.banach_tarski
