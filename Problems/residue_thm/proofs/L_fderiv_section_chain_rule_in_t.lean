-- Schwarz mixed-partial setup, chain-rule half.
-- Sub-goal `fderivwithin_h_apply10_section_hasderivwithinat` provides the same
-- chain-rule conclusion but stated as `HasDerivWithinAt` on `Icc 0 1` (the
-- natural domain on which the iterated `fderivWithin H` lives); we upgrade to
-- `HasDerivAt` here using `Set.Icc 0 1 ∈ 𝓝 t` which holds since `t ∈ Ioo 0 1`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10365

namespace Problems.residue_thm

def fderiv_section_chain_rule_in_t := @Problems.residue_thm.s10365

end Problems.residue_thm
