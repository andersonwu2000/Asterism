import Mathlib
namespace Problems.Minif2f.algebra_amgm_faxinrrp2msqrt2geq2mxm1div2x

-- amgm_x_plus_inv_2x: sq_nonneg (x - √2/2) drives nlinarith to close 2x²-2x√2+1 ≥ 0,
-- then div_nonneg + field_simp-rewrite of x+1/(2x)-√2 yields the bound.
theorem amgm_x_plus_inv_2x : ∀ x > 0, x + 1 / (2 * x) ≥ Real.sqrt 2 := by
  intro x hx
  have h1 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have h2 : 0 ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
  have hnum : 0 ≤ 2 * x ^ 2 - 2 * x * Real.sqrt 2 + 1 := by
    nlinarith [sq_nonneg (x - Real.sqrt 2 / 2)]
  have hden : (0 : ℝ) ≤ 2 * x := by linarith
  have heq : x + 1 / (2 * x) - Real.sqrt 2 =
      (2 * x ^ 2 - 2 * x * Real.sqrt 2 + 1) / (2 * x) := by field_simp; ring
  linarith [div_nonneg hnum hden, heq.symm.le.ge]

end Problems.Minif2f.algebra_amgm_faxinrrp2msqrt2geq2mxm1div2x
