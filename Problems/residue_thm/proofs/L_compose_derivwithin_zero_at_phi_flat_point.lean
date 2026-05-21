import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem compose_derivwithin_zero_at_phi_flat_point
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1)
    {t₀ : ℝ} (ht₀ : t₀ ∈ Set.Icc (0 : ℝ) 1)
    (hφdt₀ : deriv φ t₀ = 0) :
    derivWithin (γ ∘ φ) (Set.Icc 0 1) t₀ = 0 := by sorry

end Problems.residue_thm
