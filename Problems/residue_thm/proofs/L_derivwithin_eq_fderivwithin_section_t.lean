-- Slice chain rule: t-section derivWithin equals joint fderivWithin applied to (0,1).
-- Direct closure via HasFDerivWithinAt.comp_hasDerivWithinAt on the embedding
-- t' ↦ (τ', t'); Ioo ⊆ Icc lifts t ∈ Ioo into the Icc-domain of `hH`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10367

namespace Problems.residue_thm

def derivwithin_eq_fderivwithin_section_t := @Problems.residue_thm.s10367

end Problems.residue_thm
