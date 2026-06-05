import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- posdef_empty: 0×0 matrix is vacuously PosDef (no non-zero vectors in Fin 0 → ℝ)
theorem posdef_empty (M : Matrix (Fin 0) (Fin 0) ℝ) (hHerm : M.IsHermitian) :
    M.PosDef := by
  refine ⟨hHerm, fun x hx => ?_⟩
  exact absurd (Finsupp.ext (fun (i : Fin 0) => Fin.elim0 i)) hx

end Problems.LinearAlgebra.sylvester_criterion
