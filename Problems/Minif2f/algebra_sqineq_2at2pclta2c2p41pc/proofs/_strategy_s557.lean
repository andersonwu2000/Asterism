import Mathlib
import Problems.Minif2f.algebra_sqineq_2at2pclta2c2p41pc.Defs

namespace Problems.Minif2f.algebra_sqineq_2at2pclta2c2p41pc

-- Direct: rearrangement gives (a - c - 2)^2 ≥ 0, dispatched by nlinarith with sq_nonneg hint.
theorem s557 : ∀ (a c : ℝ), 2 * a * (2 + c) ≤ a ^ 2 + c ^ 2 + 4 * (1 + c)  := by
  intro a c
  nlinarith [sq_nonneg (a - c - 2), sq_nonneg (a - c), sq_nonneg (a + c), sq_nonneg a, sq_nonneg c]

end Problems.Minif2f.algebra_sqineq_2at2pclta2c2p41pc
