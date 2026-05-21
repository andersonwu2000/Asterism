import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem reparam_compose_non_integral_props
    {a : ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) ∧
    (γ ∘ φ) 0 = γ 0 ∧
    (γ ∘ φ) 1 = γ 1 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 ∧
    (∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a) := by sorry

end Problems.residue_thm
