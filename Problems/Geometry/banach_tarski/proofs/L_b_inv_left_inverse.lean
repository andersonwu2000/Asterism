import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- b_inv_left_inverse: B-generator inverse satisfies BInv * B = 1 by elementwise nlinarith
-- Uses sqrt 2 ^ 2 = 2 to reduce each entry to a rational arithmetic check.
-- entry_kind: Builder
theorem b_inv_left_inverse (B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hB : B = (1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1])
    (hBInv : BInv = (1/3:ℝ) • !![3, 0, 0; 0, 1, 2*Real.sqrt 2; 0, -2*Real.sqrt 2, 1]) :
    BInv * B = 1 := by
  subst hB hBInv
  have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Fin.sum_univ_three, Matrix.cons_val',
          Matrix.cons_val_zero, Matrix.cons_val_one] <;>
    ring_nf <;> nlinarith [h2]

end Problems.Geometry.banach_tarski
