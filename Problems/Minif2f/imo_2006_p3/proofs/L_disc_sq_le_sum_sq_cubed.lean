import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs

namespace Problems.Minif2f.imo_2006_p3

-- disc_sq_le_sum_sq_cubed: SOS bound 54·D² ≤ (Σ(a-b)²)³ via 2·((a-2b+c)(2a-b-c)(a+b-2c))² identity
theorem disc_sq_le_sum_sq_cubed : ∀ (a b c : ℝ),
    54 * ((a - b) * (b - c) * (a - c))^2
      ≤ ((a - b)^2 + (b - c)^2 + (a - c)^2)^3 := by
  intro a b c
  nlinarith [sq_nonneg ((a - 2*b + c) * (2*a - b - c) * (a + b - 2*c)),
             sq_nonneg (a - b), sq_nonneg (b - c), sq_nonneg (a - c)]

end Problems.Minif2f.imo_2006_p3
