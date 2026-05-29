import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- z_rotation_block_orthogonal: the 3×3 z-rotation block matrix satisfies Mᵀ·M = 1
-- Proved entry-by-entry using sin²+cos²=1.
theorem z_rotation_block_orthogonal (θ : ℝ) :
    Matrix.transpose
        (!![Real.cos θ, -Real.sin θ, 0;
            Real.sin θ,  Real.cos θ, 0;
            0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) *
      (!![Real.cos θ, -Real.sin θ, 0;
          Real.sin θ,  Real.cos θ, 0;
          0,           0,          1] : Matrix (Fin 3) (Fin 3) ℝ) = 1 := by
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Matrix.transpose_apply, Fin.sum_univ_three,
          Matrix.cons_val_zero, Matrix.cons_val_one, Matrix.cons_val'] <;>
    ring_nf <;>
    simp [Real.sin_sq_add_cos_sq, add_comm (Real.cos θ ^ 2) (Real.sin θ ^ 2)]


end Problems.Geometry.banach_tarski
