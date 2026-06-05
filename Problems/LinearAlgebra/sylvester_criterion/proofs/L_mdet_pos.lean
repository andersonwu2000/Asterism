import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- mdet_pos: leading principal minor at Fin.last n equals M.det by definitional equality
-- (the castLE embedding at the top index is the identity, so the submatrix is M itself)
theorem mdet_pos {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    0 < M.det := by
  exact hMinors (Fin.last n)

end Problems.LinearAlgebra.sylvester_criterion
