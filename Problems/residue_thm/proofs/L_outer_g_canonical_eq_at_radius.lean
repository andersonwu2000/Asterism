-- Reduce to radius-independence for the Cauchy kernel `w ↦ f w / (w - z)` on
-- `(dist z z₀, R)`, instantiating it at the canonical mid-radius and `r`.
-- The (2πi)⁻¹ factor cancels via `congr`/`rw`; the analytic core is the sub-goal.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10417

namespace Problems.residue_thm

def outer_g_canonical_eq_at_radius := @Problems.residue_thm.s10417

end Problems.residue_thm
