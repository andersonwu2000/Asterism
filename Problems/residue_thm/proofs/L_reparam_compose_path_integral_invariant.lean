import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem reparam_compose_path_integral_invariant
    {Q : ℂ → ℂ} {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφ0 : φ 0 = 0)
    (hφ1 : φ 1 = 1)
    (hφd0 : deriv φ 0 = 0)
    (hφd1 : deriv φ 1 = 0)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    (∫ t in (0 : ℝ)..1, Q ((γ ∘ φ) t) * deriv (γ ∘ φ) t) =
      (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t) := by sorry

end Problems.residue_thm
