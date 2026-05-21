import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_compose_avoidance_unit_interval
import Problems.residue_thm.proofs.L_compose_c1_on_unit_interval
import Problems.residue_thm.proofs.L_compose_derivwithin_zero_at_phi_flat_point

namespace Problems.residue_thm

-- Split the 6-tuple into three sub-goals: C¹-of-composition, image-avoidance,
-- and a unified endpoint chain-rule fact (derivWithin = 0 wherever deriv φ = 0).
-- The endpoint identities (γ ∘ φ) 0 = γ 0 and (γ ∘ φ) 1 = γ 1 unfold from hφ0/hφ1.
theorem s10563
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
    (∀ t ∈ Set.Icc (0 : ℝ) 1, (γ ∘ φ) t ≠ a)  := by
  have h_c1 := compose_c1_on_unit_interval hγ hφ hφrange
  have h_avoid := compose_avoidance_unit_interval havoid hφrange
  have h_d0 := compose_derivwithin_zero_at_phi_flat_point hγ hφ hφrange
    (Set.left_mem_Icc.mpr zero_le_one) hφd0
  have h_d1 := compose_derivwithin_zero_at_phi_flat_point hγ hφ hφrange
    (Set.right_mem_Icc.mpr zero_le_one) hφd1
  refine ⟨h_c1, ?_, ?_, h_d0, h_d1, h_avoid⟩
  · simp [Function.comp, hφ0]
  · simp [Function.comp, hφ1]

end Problems.residue_thm
