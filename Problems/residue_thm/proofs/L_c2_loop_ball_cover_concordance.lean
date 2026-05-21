import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c2_loop_ball_cover_concordance
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ (η : ℝ → ℂ) (n : ℕ) (t : ℕ → ℝ) (centers : ℕ → ℂ) (radii : ℕ → ℝ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = γ 0 ∧
      t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i+1)) ∧
      (∀ i, i < n → 0 < radii i) ∧
      (∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U) ∧
      (∀ i, i < n → Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i < n → Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = γ (t i)) := by sorry

end Problems.residue_thm
