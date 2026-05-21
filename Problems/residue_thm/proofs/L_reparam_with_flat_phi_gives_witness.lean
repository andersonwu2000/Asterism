import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem reparam_with_flat_phi_gives_witness
    {Q : ℂ → ℂ} {a : ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hφ : ContDiffOn ℝ 1 φ (Set.Icc 0 1))
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hdφ0 : derivWithin φ (Set.Icc 0 1) 0 = 0)
    (hdφ1 : derivWithin φ (Set.Icc 0 1) 1 = 0)
    (hφmaps : Set.MapsTo φ (Set.Icc 0 1) (Set.Icc 0 1)) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) ∧
    (γ ∘ φ) 0 = γ 0 ∧
    (γ ∘ φ) 1 = γ 1 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0 ∧
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1 = 0 ∧
    (∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a) ∧
    (∫ t in (0 : ℝ)..1, Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t) =
      (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t) := by sorry

end Problems.residue_thm
