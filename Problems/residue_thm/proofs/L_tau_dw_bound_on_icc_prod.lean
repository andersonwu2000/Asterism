-- Continuous function on the compact product `Icc 0 1 ×ˢ Icc 0 1` is bounded.
-- Sub-goal `tau_dw_integrand_continuous_on_icc_prod` packages the joint
-- continuity of the τ-derivative in (t, x); `IsCompact.exists_bound_of_continuousOn`
-- on `isCompact_Icc.prod isCompact_Icc` then yields the uniform bound, which is
-- repackaged as the double `∀ t ∀ x` conclusion via `Set.mk_mem_prod`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10351

namespace Problems.residue_thm

def tau_dw_bound_on_icc_prod := @Problems.residue_thm.s10351

end Problems.residue_thm
