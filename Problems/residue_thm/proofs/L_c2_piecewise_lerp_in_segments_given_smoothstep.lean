import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c2_piecewise_lerp_in_segments_given_smoothstep
    (σ : ℝ → ℝ) (hσC2 : ContDiff ℝ 2 σ) (hσ0 : σ 0 = 0) (hσ1 : σ 1 = 1)
    (hσrange : ∀ τ, τ ∈ Set.Icc (0:ℝ) 1 → σ τ ∈ Set.Icc (0:ℝ) 1)
    (hσd0 : deriv σ 0 = 0) (hσd1 : deriv σ 1 = 0)
    (hσdd0 : deriv (deriv σ) 0 = 0) (hσdd1 : deriv (deriv σ) 1 = 0)
    {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1))
    (hp_collapse : ∀ i, i < n → t i = t (i + 1) → p i = p (i + 1)) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      (∀ i, i ≤ n → η (t i) = p i) ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1)))) := by sorry

end Problems.residue_thm
