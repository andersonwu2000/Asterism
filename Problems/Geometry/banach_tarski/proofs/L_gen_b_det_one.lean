import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- gen_b_det_one: det of (1/3)•B generator matrix = 1
theorem gen_b_det_one :
    ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 1 := by
  simp [Matrix.det_fin_three]
  ring_nf
  norm_num [Real.sq_sqrt]
end Problems.Geometry.banach_tarski
