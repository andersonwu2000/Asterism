import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- mdet_pos_2: det M > 0 follows because leadingPrincipalMinor M (Fin.last n) is
-- definitionally equal to M.det (castLE at Fin.last n is the identity on Fin (n+1)).
theorem mdet_pos_2 {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    0 < M.det := by exact hMinors (Fin.last n)

end Problems.LinearAlgebra.sylvester_criterion
