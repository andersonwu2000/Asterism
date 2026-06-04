import Mathlib
import Problems.Minif2f.amc12a_2008_p8.Defs

namespace Problems.Minif2f.amc12a_2008_p8

-- y_eq_one: factor y³-1=(y-1)(y²+y+1); positivity rules out the second factor since y>0
theorem y_eq_one : ∀ (y : ℝ), 0 < y → y ^ 3 = 1 → y = 1 := by
  intro y hy hy3
  have h1 : y ^ 2 + y + 1 > 0 := by positivity
  have h2 : (y - 1) * (y ^ 2 + y + 1) = 0 := by ring_nf; linarith
  rcases mul_eq_zero.mp h2 with h | h
  · linarith
  · linarith

end Problems.Minif2f.amc12a_2008_p8
