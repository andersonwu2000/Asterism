import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct chain rule at endpoint 0: deriv φ 0 = 0 forces (γ∘φ)' = (deriv φ 0) • γ' = 0.
-- Builds HasDerivWithinAt for φ (from HasDerivAt via C¹) and γ at φ 0 ∈ Icc (from C¹ on Icc),
-- composes via HasDerivWithinAt.scomp, then promotes to derivWithin via uniqueDiffOn_Icc.
theorem s10610
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    (hφd0 : deriv φ 0 = 0) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 0 = 0  := by
  have hφ_at : HasDerivAt φ (deriv φ 0) 0 :=
    (hφ.differentiable one_ne_zero).differentiableAt.hasDerivAt
  rw [hφd0] at hφ_at
  have hφ_within : HasDerivWithinAt φ 0 (Set.Icc 0 1) 0 := hφ_at.hasDerivWithinAt
  have hφ0_mem : φ 0 ∈ Set.Icc (0 : ℝ) 1 := hφrange 0 (Set.left_mem_Icc.mpr zero_le_one)
  have hγ_diff : DifferentiableWithinAt ℝ γ (Set.Icc 0 1) (φ 0) :=
    hγ.differentiableOn one_ne_zero (φ 0) hφ0_mem
  have hγ_within : HasDerivWithinAt γ (derivWithin γ (Set.Icc 0 1) (φ 0)) (Set.Icc 0 1) (φ 0) :=
    hγ_diff.hasDerivWithinAt
  have h_maps : Set.MapsTo φ (Set.Icc 0 1) (Set.Icc 0 1) := hφrange
  have h_comp : HasDerivWithinAt (γ ∘ φ) ((0 : ℝ) • derivWithin γ (Set.Icc 0 1) (φ 0))
      (Set.Icc 0 1) 0 := hγ_within.scomp 0 hφ_within h_maps
  have h_zero : ((0 : ℝ) • derivWithin γ (Set.Icc 0 1) (φ 0) : ℂ) = 0 := by
    simp
  rw [h_zero] at h_comp
  exact h_comp.derivWithin ((uniqueDiffOn_Icc zero_lt_one) 0 (Set.left_mem_Icc.mpr zero_le_one))

end Problems.residue_thm
