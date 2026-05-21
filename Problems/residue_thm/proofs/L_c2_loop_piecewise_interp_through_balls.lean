import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c2_loop_piecewise_interp_through_balls
    {U : Set ℂ} {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ) (centers : ℕ → ℂ) (radii : ℕ → ℝ)
    (hU : IsOpen U)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i+1))
    (hrpos : ∀ i, i < n → 0 < radii i)
    (hballsubU : ∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U)
    (hp_in_ball : ∀ i, i < n → p i ∈ Metric.ball (centers i) (radii i))
    (hp_next_in_ball : ∀ i, i < n → p (i+1) ∈ Metric.ball (centers i) (radii i))
    (hp_loop : p n = p 0) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = p 0 ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = p i) := by sorry

end Problems.residue_thm
