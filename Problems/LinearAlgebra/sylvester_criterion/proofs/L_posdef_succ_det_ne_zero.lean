import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- posdef_succ_det_ne_zero: last leading principal minor equals M.det, so positivity implies det ≠ 0
theorem posdef_succ_det_ne_zero {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.det ≠ 0 := by
  have hlast := hMinors (Fin.last n)
  have heq : leadingPrincipalMinor M (Fin.last n) = M.det := by
    simp [leadingPrincipalMinor, Fin.last]
  linarith [heq ▸ hlast]

end Problems.LinearAlgebra.sylvester_criterion
