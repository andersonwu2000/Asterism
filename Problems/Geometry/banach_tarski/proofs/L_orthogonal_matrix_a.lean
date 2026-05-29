import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- orthogonal_matrix_a: Aᵀ * A = 1 for concrete rotation generator A via sq_sqrt + nlinarith
-- Substitutes the explicit definition of A, expands entry-by-entry with Fin.sum_univ_three,
-- then closes each of the 9 scalar goals using nlinarith with the key fact √2 ^ 2 = 2.
theorem orthogonal_matrix_a (A : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3]) :
    Matrix.transpose A * A = 1 := by
  have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  subst hA
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply] <;>
    nlinarith [h2]

end Problems.Geometry.banach_tarski
