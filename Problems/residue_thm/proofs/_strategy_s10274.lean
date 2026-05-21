import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct: `windingNumber γ a` is defined as `Classical.choose h` under the same
-- existence hypothesis. `unfold` + `dif_pos h` + `Classical.choose_spec h` closes the goal.
theorem s10274
    (γ : ℝ → ℂ) (a : ℂ)
    (h : ∃ k : ℤ,
          (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k) :
    (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * (Complex.windingNumber γ a : ℂ)  := by
  unfold Complex.windingNumber
  rw [dif_pos h]
  exact Classical.choose_spec h

end Problems.residue_thm
