-- Adapted from homotopy_integrand_intervalintegrable: build continuity of P a ∘ γ via
-- composition (γ avoids a since γ : Icc 0 1 → U \ T and a ∈ T), then use the
-- derivWithin trick (continuous derivWithin on Icc + congr_ae) to switch to deriv γ.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10461

namespace Problems.residue_thm

def principal_along_path_intvl_integrable := @Problems.residue_thm.s10461

end Problems.residue_thm
