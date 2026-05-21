import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem h_deriv_integral
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt (fun s => ∫ t in (0:ℝ)..s, deriv γ t / (γ t - a))
        (deriv γ s / (γ s - a)) (Set.Icc (0:ℝ) 1) s := by sorry

end Problems.residue_thm
