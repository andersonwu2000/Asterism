-- Translate `deriv ... τ` at fixed τ ∈ Ioo 0 1 into the `derivWithin (Icc 0 1) τ`
-- formulation pointwise on t ∈ Ioo 0 1 (proved sibling `tau_deriv_eq_dw_on_ioo_prod`),
-- then close by `ContinuousOn.congr` against the section-continuity sub-goal in the
-- derivWithin form (`dw_integrand_section_cont_on_ioo`), which is structurally amenable
-- to slicing the joint `ContinuousOn (Icc×Icc)` of the integrand.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10354

namespace Problems.residue_thm

def homotopy_partial_tau_continuous_on_ioo := @Problems.residue_thm.s10354

end Problems.residue_thm
