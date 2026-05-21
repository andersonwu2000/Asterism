import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_arch_unit_interval_mesh_partition
import Problems.residue_thm.proofs.L_path_modulus_uc_compact_icc

namespace Problems.residue_thm

-- Heine-Cantor modulus + Archimedean uniform mesh: (A) γ on compact Icc 0 1 yields
-- η > 0 with |s - t| < η ⇒ dist (γ s) (γ t) < δ; (B) [0,1] admits a partition with
-- mesh < η. For s ∈ [t i, t (i+1)] ⊆ [0,1], |s - t i| < η so each subarc maps into
-- Metric.ball (γ (t i)) δ pointwise.
theorem s10503
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (δ : ℝ) (hδ : 0 < δ) :
    ∃ (n : ℕ) (t : ℕ → ℝ), t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i+1)) ∧
      (∀ i, i ≤ n → t i ∈ Set.Icc (0:ℝ) 1) ∧
      (∀ i, i < n →
        Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (γ (t i)) δ))  := by
  obtain ⟨η, hη_pos, hη_uc⟩ := path_modulus_uc_compact_icc hγ δ hδ
  obtain ⟨n, t, ht0, htn, hmono, hin, hmesh⟩ := arch_unit_interval_mesh_partition η hη_pos
  refine ⟨n, t, ht0, htn, hmono, hin, ?_⟩
  intro i hi s hs
  have hti : t i ∈ Set.Icc (0:ℝ) 1 := hin i hi.le
  have hti1 : t (i+1) ∈ Set.Icc (0:ℝ) 1 := hin (i+1) hi
  have hs01 : s ∈ Set.Icc (0:ℝ) 1 :=
    ⟨le_trans hti.1 hs.1, le_trans hs.2 hti1.2⟩
  have hdiff : |s - t i| < η := by
    rw [abs_of_nonneg (sub_nonneg.mpr hs.1)]
    linarith [hs.2, hmesh i hi]
  exact Metric.mem_ball.mpr (hη_uc s hs01 (t i) hti hdiff)

end Problems.residue_thm
