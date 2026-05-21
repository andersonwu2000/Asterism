import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem gamma_circ_phi_at_one
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hφ1 : φ 1 = 1) :
    (γ ∘ φ) 1 = γ 1 := by simp_all only [Function.comp_apply]

end Problems.residue_thm
