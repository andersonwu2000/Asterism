import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs.L_value_x531
import Problems.Minif2f.aimeII_2001_p3.proofs.L_value_x753
import Problems.Minif2f.aimeII_2001_p3.proofs.L_value_x975

namespace Problems.Minif2f.aimeII_2001_p3

-- Decompose: split the triple sum into three independent value computations,
-- then close by linarith. Each sub-goal isolates one index (531, 753, 975) so
-- a separate periodicity argument can be applied to each without interference.
theorem s548 : ∀ (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420) (h₄ : x 4 = 523) (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)), x 531 + x 753 + x 975 = 898  := by
  intro x h₀ h₂ h₃ h₄ h₆
  have h_x531 : x 531 = 211 := value_x531 x h₀ h₂ h₃ h₄ h₆
  have h_x753 : x 753 = 420 := value_x753 x h₀ h₂ h₃ h₄ h₆
  have h_x975 : x 975 = 267 := value_x975 x h₀ h₂ h₃ h₄ h₆
  linarith

end Problems.Minif2f.aimeII_2001_p3
