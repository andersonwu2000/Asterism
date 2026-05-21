import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- gamma_circ_phi_contdiffon_unit: C¹ composition of C¹ path γ with C¹ reparametrization φ
theorem gamma_circ_phi_contdiffon_unit
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) := by
  exact hγ.comp hφ.contDiffOn (fun t ht => hφrange t ht)


end Problems.residue_thm
