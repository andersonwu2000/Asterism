import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem family_of_smooth_blend_segment_pieces
    (σ : ℝ → ℝ) (hσC2 : ContDiff ℝ 2 σ) (hσ0 : σ 0 = 0) (hσ1 : σ 1 = 1)
    (hσrange : ∀ τ, τ ∈ Set.Icc (0:ℝ) 1 → σ τ ∈ Set.Icc (0:ℝ) 1)
    (hσd0 : deriv σ 0 = 0) (hσd1 : deriv σ 1 = 0)
    (hσdd0 : deriv (deriv σ) 0 = 0) (hσdd1 : deriv (deriv σ) 1 = 0)
    {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1)) :
    ∃ ψ : ℕ → ℝ → ℂ,
      ∀ i, i < n →
        ContDiffOn ℝ 2 (ψ i) (Set.Icc (t i) (t (i + 1))) ∧
        ψ i (t i) = p i ∧
        ψ i (t (i + 1)) = p (i + 1) ∧
        Set.MapsTo (ψ i) (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1))) ∧
        derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))) (t i) = 0 ∧
        derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))) (t (i + 1)) = 0 ∧
        derivWithin (derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))))
            (Set.Icc (t i) (t (i + 1))) (t i) = 0 ∧
        derivWithin (derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))))
            (Set.Icc (t i) (t (i + 1))) (t (i + 1)) = 0 := by sorry

end Problems.residue_thm
