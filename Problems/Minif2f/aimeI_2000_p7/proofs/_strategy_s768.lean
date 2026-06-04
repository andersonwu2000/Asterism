import Mathlib
import Problems.Minif2f.aimeI_2000_p7.Defs
import Problems.Minif2f.aimeI_2000_p7.proofs.L_m_eq_one_quarter

namespace Problems.Minif2f.aimeI_2000_p7

-- Decompose: single sub-goal `m_eq_one_quarter` derives `m = 1/4`
-- from the AIME system; the parent then reduces to the concrete
-- numeric identity `↑(1/4).den + (1/4).num = 5` (= 4 + 1), closed by
-- `native_decide` (only style-linter warning; not an error).
theorem s768 : ∀ (x y z : ℝ) (m : ℚ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : x * y * z = 1) (h₂ : x + 1 / z = 5) (h₃ : y + 1 / x = 29) (h₄ : z + 1 / y = m) (h₅ : 0 < m), ↑m.den + m.num = 5  := by
  intro x y z m h₀ h₁ h₂ h₃ h₄ h₅
  have h_eq : m = 1/4 := m_eq_one_quarter x y z m h₀ h₁ h₂ h₃ h₄ h₅
  rw [h_eq]
  native_decide

end Problems.Minif2f.aimeI_2000_p7
