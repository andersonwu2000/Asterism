import Mathlib
import Problems.Minif2f.aimeI_2000_p7.Defs
import Problems.Minif2f.aimeI_2000_p7.proofs.L_x_eq_one_fifth
import Problems.Minif2f.aimeI_2000_p7.proofs.L_y_eq_twenty_four
import Problems.Minif2f.aimeI_2000_p7.proofs.L_z_eq_five_over_twentyfour

namespace Problems.Minif2f.aimeI_2000_p7

-- Decompose: extract x = 1/5, y = 24, z = 5/24 from the positive AIME system,
-- then substitute into h₄ : z + 1/y = ↑m to reduce to (↑m : ℝ) = 1/4, then
-- cast back to ℚ. Each sub-goal is independent of m, h₄, h₅.
theorem s9395 : ∀ (x y z : ℝ) (m : ℚ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : x * y * z = 1) (h₂ : x + 1 / z = 5) (h₃ : y + 1 / x = 29) (h₄ : z + 1 / y = m) (h₅ : 0 < m), m = 1/4  := by
  intro x y z m h₀ h₁ h₂ h₃ h₄ h₅
  have hx : x = 1/5 := x_eq_one_fifth x y z m h₀ h₁ h₂ h₃ h₄ h₅
  have hy : y = 24 := y_eq_twenty_four x y z m h₀ h₁ h₂ h₃ h₄ h₅
  have hz : z = 5/24 := z_eq_five_over_twentyfour x y z m h₀ h₁ h₂ h₃ h₄ h₅
  rw [hy, hz] at h₄
  have hmreal : ((m : ℝ)) = ((1/4 : ℚ) : ℝ) := by push_cast; linarith
  exact_mod_cast hmreal

end Problems.Minif2f.aimeI_2000_p7
