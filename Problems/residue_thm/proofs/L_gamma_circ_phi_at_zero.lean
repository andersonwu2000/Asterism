import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem gamma_circ_phi_at_zero
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hφ0 : φ 0 = 0) :
    (γ ∘ φ) 0 = γ 0 := by simp_all only [Function.comp_apply]

end Problems.residue_thm
