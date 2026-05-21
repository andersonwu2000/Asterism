import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- path_modulus_uc_compact_icc: Heine-Cantor gives η>0 with |s-t|<η ⇒ dist(γ s)(γ t)<δ
-- Uses IsCompact.uniformContinuousOn_of_continuous on Icc 0 1 + Real.dist_eq.
theorem path_modulus_uc_compact_icc
    {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (δ : ℝ) (hδ : 0 < δ) :
    ∃ η : ℝ, 0 < η ∧ ∀ s ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      |s - t| < η → dist (γ s) (γ t) < δ := by
  have hcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have huc := isCompact_Icc.uniformContinuousOn_of_continuous hcont
  rw [Metric.uniformContinuousOn_iff] at huc
  obtain ⟨η, hη, hball⟩ := huc δ hδ
  exact ⟨η, hη, fun s hs t ht hst => hball s hs t ht (by rwa [Real.dist_eq])⟩

end Problems.residue_thm
