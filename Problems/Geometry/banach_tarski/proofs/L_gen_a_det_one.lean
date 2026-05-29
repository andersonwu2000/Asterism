import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- gen_a_det_one: det((1/3)•A) = 1 via Matrix.det_smul + explicit cofactor expansion + √2²=2
-- Uses rfl for third-row vector entries (Fin 3 index 2), simp for vecCons residual,
-- and nlinarith with hsq to close 3 + 12*(√2*√2) = 27.
theorem gen_a_det_one :
    ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 1 := by
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  have hdet : (!![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 27 := by
    rw [Matrix.det_fin_three]
    have hv1 : (![1, -(2 * Real.sqrt 2), 0] : Fin 3 → ℝ) 2 = 0 := rfl
    have hv2 : (![2 * Real.sqrt 2, 1, 0] : Fin 3 → ℝ) 2 = 0 := rfl
    have hv3 : (![0, 0, 3] : Fin 3 → ℝ) 2 = 3 := rfl
    norm_num [hv1, hv2, hv3, Matrix.cons_val_succ, Matrix.cons_val_zero]
    have hc : Matrix.vecCons (0:ℝ)
        (fun i : Fin 2 ↦ Matrix.vecCons (0:ℝ) (fun _ : Fin 1 ↦ (3:ℝ)) i) (2:Fin 3) = 3 := by
      simp
    nlinarith [hsq, hc]
  have hsmul : ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det =
      (1/3:ℝ)^3 * (!![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det := Matrix.det_smul _ _
  rw [hsmul, hdet]
  norm_num

end Problems.Geometry.banach_tarski
