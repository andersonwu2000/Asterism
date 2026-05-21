import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- derivwithin_gamma_comp_phi_chain_at_one: chain rule for derivWithin (γ∘φ) at 1
-- Uses derivWithin.scomp (ℝ-vector-valued scomp variant) then Complex.real_smul + mul_comm
-- to bridge r • z = z * ↑r (ℝ-smul on ℂ) matching the coerced RHS.
theorem derivwithin_gamma_comp_phi_chain_at_one
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) 1
      = derivWithin γ (Set.Icc 0 1) (φ 1) * derivWithin φ (Set.Icc 0 1) 1 := by
  have hmem : (1 : ℝ) ∈ Set.Icc (0 : ℝ) 1 := Set.right_mem_Icc.mpr zero_le_one
  have hφ1mem : φ 1 ∈ Set.Icc (0 : ℝ) 1 := hφrange 1 hmem
  have hDγ : DifferentiableWithinAt ℝ γ (Set.Icc 0 1) (φ 1) :=
    hγ.differentiableOn one_ne_zero _ hφ1mem
  have hDφ : DifferentiableWithinAt ℝ φ (Set.Icc 0 1) 1 :=
    (hφ.differentiable one_ne_zero).differentiableAt.differentiableWithinAt
  have hMaps : Set.MapsTo φ (Set.Icc 0 1) (Set.Icc 0 1) := hφrange
  rw [derivWithin.scomp (1 : ℝ) hDγ hDφ hMaps]
  exact Complex.real_smul.trans (mul_comm _ _)

end Problems.residue_thm
