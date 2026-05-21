-- Split the primitive-existence into (1) closed-loop integrals vanish on ℂ\{a}
-- (uses analyticity + residue 0 + decay-at-∞, via Cauchy / principal-part / Liouville)
-- and (2) the abstract Morera-style construction of a primitive from the
-- closed-loop-zero hypothesis (uses path-independence of line integrals).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10485

namespace Problems.residue_thm

def primitive_punctured_of_decay_residue_zero := @Problems.residue_thm.s10485

end Problems.residue_thm
