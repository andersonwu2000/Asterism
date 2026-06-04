import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs
import Problems.Minif2f.imo_2006_p3.proofs.L_cubed_linear_am_gm
import Problems.Minif2f.imo_2006_p3.proofs.L_disc_sq_le_sum_sq_cubed

namespace Problems.Minif2f.imo_2006_p3

-- Two-step SOS bridge for the squared IMO 2006 polynomial inequality.
-- (A) `54·D² ≤ ((a-b)²+(b-c)²+(a-c)²)³` (D = (a-b)(b-c)(a-c)) — pure SOS
--     identity: RHS − LHS = 2·((a-2b+c)(2a-b-c)(a+b-2c))² ≥ 0.
-- (B) `256·u³·v ≤ 27·(u+v)⁴` for all reals u,v — pure SOS identity
--     RHS − LHS = (u−3v)²·(27u²+14uv+3v²) with both factors SOS.
-- Combine with u = ((a-b)²+(b-c)²+(a-c)²) = 3(a²+b²+c²)−(a+b+c)², v = (a+b+c)²:
-- ×v on A: 54·D²·v ≤ u³·v; ×256 then chain B: 13824·D²·v ≤ 27·(u+v)⁴.
-- Since u+v = 3(a²+b²+c²), RHS = 2187·(a²+b²+c²)⁴; divide by 27.
theorem s9617 : ∀ (a b c : ℝ),
    512 * ((a - b) * (b - c) * (a - c) * (a + b + c))^2
      ≤ 81 * (a^2 + b^2 + c^2)^4  := by
  intro a b c
  have hA := disc_sq_le_sum_sq_cubed a b c
  have hB := cubed_linear_am_gm ((a-b)^2 + (b-c)^2 + (a-c)^2) ((a+b+c)^2)
  have hv_nn : (0 : ℝ) ≤ (a+b+c)^2 := sq_nonneg _
  have step1 : 54 * ((a-b)*(b-c)*(a-c))^2 * (a+b+c)^2
             ≤ ((a-b)^2 + (b-c)^2 + (a-c)^2)^3 * (a+b+c)^2 :=
    mul_le_mul_of_nonneg_right hA hv_nn
  have rhs_eq : 27 * (((a-b)^2 + (b-c)^2 + (a-c)^2) + (a+b+c)^2)^4
              = 2187 * (a^2 + b^2 + c^2)^4 := by ring
  have lhs_eq : ((a-b)*(b-c)*(a-c)*(a+b+c))^2
              = ((a-b)*(b-c)*(a-c))^2 * (a+b+c)^2 := by ring
  rw [lhs_eq]
  linarith [step1, hB, rhs_eq]

end Problems.Minif2f.imo_2006_p3
