-- Slice the (already-declared open sibling) joint τ-derivWithin integrand
-- continuity on `Icc 0 1 ×ˢ Icc 0 1` along `t ↦ (t, τ)`; since `Ioo ⊆ Icc`,
-- the slice map is continuous on `Ioo 0 1` and lands in the product, so the
-- composition closes the goal directly via `ContinuousOn.comp`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10362

namespace Problems.residue_thm

def dw_integrand_section_cont_on_ioo := @Problems.residue_thm.s10362

end Problems.residue_thm
