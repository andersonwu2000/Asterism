import Mathlib
import Problems.Minif2f.mathd_numbertheory_780.Defs

namespace Problems.Minif2f.mathd_numbertheory_780

-- m_dvd_215: interval_cases on bounded m in [10,99], omega closes each case via
-- modular arithmetic constraints (h₂: 6x%m=1, h₃: (x-36)%m=0 → m∣215).
theorem m_dvd_215 : ∀ (m x : ℤ) (h₀ : 0 ≤ x) (h₁ : 10 ≤ m ∧ m ≤ 99)
    (h₂ : 6 * x % m = 1) (h₃ : (x - 6 ^ 2) % m = 0), m ∣ 215 := by
  intro m x h₀ h₁ h₂ h₃
  have hm1 : 10 ≤ m := h₁.1
  have hm2 : m ≤ 99 := h₁.2
  interval_cases m <;> omega

end Problems.Minif2f.mathd_numbertheory_780
