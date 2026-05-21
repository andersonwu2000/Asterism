import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem chain_rule_g_circ_gamma_on_uicc
    {U : Set ℂ} {γ : ℝ → ℂ} {g G : ℂ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) U)
    (hG : ∀ z ∈ U, HasDerivAt G (g z) z) :
    ∀ t ∈ Set.uIcc (0:ℝ) 1,
      HasDerivAt (fun s => G (γ s)) (g (γ t) * deriv γ t) t := by sorry

end Problems.residue_thm
