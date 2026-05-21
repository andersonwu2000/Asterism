import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_partition_endpoints_in_unit_interval
import Problems.residue_thm.proofs.L_path_int_eq_diff_on_ball_subinterval

namespace Problems.residue_thm

-- Per-piece FTC on a ball: g admits a primitive F on B_i ⊆ U via
-- DifferentiableOn.isExactOn_ball; FTC on the sub-interval [t i, t (i+1)]
-- reduces each integral to F at endpoints, which agree by h_agree.
theorem s10502
    {U : Set ℂ} {g : ℂ → ℂ} {γ η : ℝ → ℂ}
    {n : ℕ} {t : ℕ → ℝ} {centers : ℕ → ℂ} {radii : ℕ → ℝ}
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hη : ContDiffOn ℝ 1 η (Set.Icc 0 1))
    (ht0 : t 0 = 0) (htn : t n = 1)
    (ht_mono : ∀ i, i < n → t i ≤ t (i + 1))
    (hball_sub : ∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U)
    (hγ_in : ∀ i, i < n →
      Set.MapsTo γ (Set.Icc (t i) (t (i + 1))) (Metric.ball (centers i) (radii i)))
    (hη_in : ∀ i, i < n →
      Set.MapsTo η (Set.Icc (t i) (t (i + 1))) (Metric.ball (centers i) (radii i)))
    (h_agree : ∀ i, i ≤ n → η (t i) = γ (t i))
    (i : ℕ) (hi : i < n) :
    (∫ s in t i..t (i + 1), g (γ s) * deriv γ s) =
    (∫ s in t i..t (i + 1), g (η s) * deriv η s)  := by
  have hball_sub_i := hball_sub i hi
  have hγ_in_i := hγ_in i hi
  have hη_in_i := hη_in i hi
  have h_eq_start : η (t i) = γ (t i) := h_agree i hi.le
  have h_eq_end : η (t (i + 1)) = γ (t (i + 1)) := h_agree (i + 1) hi
  have hg_ball : DifferentiableOn ℂ g (Metric.ball (centers i) (radii i)) :=
    (hg.mono hball_sub_i).differentiableOn
  obtain ⟨F, hF⟩ := hg_ball.isExactOn_ball
  have hab : t i ≤ t (i + 1) := ht_mono i hi

  have hbnds : 0 ≤ t i ∧ t (i + 1) ≤ 1 :=
    partition_endpoints_in_unit_interval ht0 htn ht_mono i hi
  have hsub : Set.Icc (t i) (t (i + 1)) ⊆ Set.Icc (0 : ℝ) 1 :=
    Set.Icc_subset_Icc hbnds.1 hbnds.2
  have hγ_sub : ContDiffOn ℝ 1 γ (Set.Icc (t i) (t (i + 1))) := hγ.mono hsub
  have hη_sub : ContDiffOn ℝ 1 η (Set.Icc (t i) (t (i + 1))) := hη.mono hsub
  have hγ_int := path_int_eq_diff_on_ball_subinterval hab hF hγ_sub hγ_in_i
  have hη_int := path_int_eq_diff_on_ball_subinterval hab hF hη_sub hη_in_i
  rw [hγ_int, hη_int, ← h_eq_start, ← h_eq_end]

end Problems.residue_thm
