import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- orthogonal_matrix_b: Bᵀ * B = 1 for the second rotation generator via component-wise nlinarith
-- Substitutes the explicit scalar-matrix form of B, introduces √2·√2=2 as hsq,
-- then closes all 9 matrix entries with fin_cases + simp + ring_nf + nlinarith.
theorem orthogonal_matrix_b (B : Matrix (Fin 3) (Fin 3) ℝ)
    (hB : B = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1]) :
    Matrix.transpose B * B = 1 := by
  subst hB
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply,
          Matrix.cons_val_zero, Matrix.cons_val_one] <;>
    ring_nf <;>
    nlinarith [hsq, sq_nonneg (Real.sqrt 2)]

end Problems.Geometry.banach_tarski
