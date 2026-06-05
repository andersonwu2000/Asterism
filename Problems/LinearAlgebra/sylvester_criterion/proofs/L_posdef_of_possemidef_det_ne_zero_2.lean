import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_of_possemidef_det_ne_zero

namespace Problems.LinearAlgebra.sylvester_criterion

theorem posdef_of_possemidef_det_ne_zero_2 {n : Type*} [Fintype n] [DecidableEq n]
    {M : Matrix n n ℝ} (hM : M.PosSemidef) (hd : M.det ≠ 0) : M.PosDef := by apply posdef_of_possemidef_det_ne_zero <;> assumption

end Problems.LinearAlgebra.sylvester_criterion
