import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem analytic_path_int_zero_given_ball_cover
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    {n : ℕ} {t : ℕ → ℝ} {c : ℕ → ℂ} {r : ℕ → ℝ}
    (ht0 : t 0 = 0)
    (htn : t n = 1)
    (hmono : ∀ i, i < n → t i ≤ t (i + 1))
    (hpos : ∀ i, i < n → 0 < r i)
    (hball : ∀ i, i < n → Metric.ball (c i) (r i) ⊆ U)
    (hseg : ∀ i, i < n →
      Set.MapsTo γ (Set.Icc (t i) (t (i + 1))) (Metric.ball (c i) (r i))) :
    (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 := by sorry

end Problems.residue_thm
