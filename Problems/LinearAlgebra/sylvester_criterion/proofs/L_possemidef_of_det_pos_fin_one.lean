import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- possemidef_of_det_pos_fin_one: 1×1 real matrix with positive det is PosSemidef
-- via diagonal rewrite: every 1×1 matrix is diagonal, then use posSemidef_diagonal_iff
theorem possemidef_of_det_pos_fin_one (S : Matrix (Fin 1) (Fin 1) ℝ)
    (h : 0 < S.det) : S.PosSemidef := by
  have hS0 : 0 < S 0 0 := Matrix.det_fin_one S ▸ h
  have hS_diag : S = Matrix.diagonal (fun _ => S 0 0) := by
    ext i j; fin_cases i; fin_cases j; simp [Matrix.diagonal]
  rw [hS_diag, Matrix.posSemidef_diagonal_iff]
  intro i; fin_cases i; exact le_of_lt hS0
end Problems.LinearAlgebra.sylvester_criterion
