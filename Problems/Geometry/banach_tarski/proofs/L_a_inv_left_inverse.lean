import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- a_inv_left_inverse: Matrix.mul_self_sqrt + fin_cases element-check closes AInv * A = 1
-- Substitute both definitions, establish sqrt2 * sqrt2 = 2, then verify each of the 9 entries
-- entry_kind: Builder
theorem a_inv_left_inverse (A AInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1/3:ℝ) • !![1, 2*Real.sqrt 2, 0; -2*Real.sqrt 2, 1, 0; 0, 0, 3]) :
    AInv * A = 1 := by
  subst hA hAInv
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Matrix.smul_apply, Fin.sum_univ_three] <;>
    ring_nf <;>
    nlinarith

end Problems.Geometry.banach_tarski
