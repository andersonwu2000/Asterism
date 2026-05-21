-- Split the conjunctive existential by isolating the value equation from the
-- analyticity / tendsto conjuncts. Sub-goal 1 produces any P satisfying the
-- pointwise integral identity (radii-independent witness). Sub-goals 2 and 3
-- take such a P as hypothesis and derive analyticity on `ℂ \ {z₀}` and decay
-- at cocompact respectively. Each sub-goal drops two of the three conjuncts,
-- so each is strictly simpler than the parent ∃-conjunction.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10412

namespace Problems.residue_thm

def inner_principal_part_exists := @Problems.residue_thm.s10412

end Problems.residue_thm
