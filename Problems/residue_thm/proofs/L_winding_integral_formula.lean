import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exists_winding_integer

namespace Problems.residue_thm

-- winding_integral_formula: unfold windingNumber def, apply exists_winding_integer
-- (integrality of log-deriv over closed C¹ path), then Classical.choose_spec closes.
theorem winding_integral_formula
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))
      = 2 * Real.pi * Complex.I * (Complex.windingNumber γ a : ℂ) := by
  unfold Complex.windingNumber
  have h_exists : ∃ k : ℤ, (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * (k : ℂ) :=
    exists_winding_integer hγ hclosed h_avoid
  rw [dif_pos h_exists]
  exact Classical.choose_spec h_exists

end Problems.residue_thm
