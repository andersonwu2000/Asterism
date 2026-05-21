import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_uniform_continuity_modulus_path
import Problems.residue_thm.proofs.L_unit_interval_partition_with_mesh

namespace Problems.residue_thm

-- Decompose via Heine-Cantor + interval-partition: (A) γ on the compact Icc 0 1 is uniformly
-- continuous so some η > 0 satisfies |s - t| < η ⇒ dist (γ s) (γ t) < δ; (B) the unit interval
-- admits a partition with mesh < η. Combining: for s ∈ [t i, t (i+1)] ⊆ [0,1], |s - t i| < η so
-- the per-segment MapsTo into Metric.ball (γ (t i)) δ follows pointwise.
theorem s10500
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
  obtain ⟨η, hη_pos, hη_uc⟩ := uniform_continuity_modulus_path hγ δ hδ
  obtain ⟨n, t, ht0, htn, hmono, hin, hmesh⟩ := unit_interval_partition_with_mesh η hη_pos
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

