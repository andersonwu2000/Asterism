import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem smooth_blend_segment_single_piece_collapse_aware
    (σ : ℝ → ℝ) (hσC2 : ContDiff ℝ 2 σ) (hσ0 : σ 0 = 0) (hσ1 : σ 1 = 1)
    (hσrange : ∀ τ, τ ∈ Set.Icc (0:ℝ) 1 → σ τ ∈ Set.Icc (0:ℝ) 1)
    (hσd0 : deriv σ 0 = 0) (hσd1 : deriv σ 1 = 0)
    (hσdd0 : deriv (deriv σ) 0 = 0) (hσdd1 : deriv (deriv σ) 1 = 0) :
    ∀ (a b : ℝ) (u v : ℂ), a ≤ b → (a = b → u = v) → ∃ f : ℝ → ℂ,
      ContDiffOn ℝ 2 f (Set.Icc a b) ∧
      f a = u ∧
      f b = v ∧
      Set.MapsTo f (Set.Icc a b) (segment ℝ u v) ∧
      derivWithin f (Set.Icc a b) a = 0 ∧
      derivWithin f (Set.Icc a b) b = 0 ∧
      derivWithin (derivWithin f (Set.Icc a b)) (Set.Icc a b) a = 0 ∧
      derivWithin (derivWithin f (Set.Icc a b)) (Set.Icc a b) b = 0 := by sorry

end Problems.residue_thm
