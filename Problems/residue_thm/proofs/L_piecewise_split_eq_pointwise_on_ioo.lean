-- Strip α' 0 via add_assoc, reducing to a clean integral identity:
-- ∫ piecewise on (0,u) = ∫ alpha-branch on (0,1/2) + ∫ beta-branch on (1/2,u).
-- The sub-goal piecewise_integral_split_clean_on_ioo carries that identity.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10685

namespace Problems.residue_thm

def piecewise_split_eq_pointwise_on_ioo := @Problems.residue_thm.s10685

end Problems.residue_thm
