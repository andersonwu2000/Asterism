-- Split the 6-conjunct conclusion into six independent sub-goals (one per conjunct):
-- C¹ composition, endpoint identities at 0 and 1, flat-derivWithin at 0 and 1
-- (via the φ-flat-at-endpoint hypothesis), and pointwise avoidance through φrange.
-- Each sub-goal carries only the hypotheses it needs; the parent combines them with
-- `⟨…⟩`. Reduces a tuple goal to strictly simpler component lemmas.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10591

namespace Problems.residue_thm

def reparam_compose_c1_non_integral_props_v2 := @Problems.residue_thm.s10591

end Problems.residue_thm
