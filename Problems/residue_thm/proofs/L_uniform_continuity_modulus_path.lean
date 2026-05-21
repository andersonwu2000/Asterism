import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- uniform_continuity_modulus_path: Heine-Cantor on compact Icc 0 1 yields the η modulus
theorem uniform_continuity_modulus_path
    {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (δ : ℝ) (hδ : 0 < δ) :
    ∃ η : ℝ, 0 < η ∧ ∀ s ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
      |s - t| < η → dist (γ s) (γ t) < δ := by
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have huc : UniformContinuousOn γ (Set.Icc 0 1) :=
    isCompact_Icc.uniformContinuousOn_of_continuous hγcont
  rw [Metric.uniformContinuousOn_iff] at huc
  obtain ⟨η, hη_pos, hη⟩ := huc δ hδ
  exact ⟨η, hη_pos, fun s hs t ht hst => hη s hs t ht (by rwa [Real.dist_eq])⟩

end Problems.residue_thm
