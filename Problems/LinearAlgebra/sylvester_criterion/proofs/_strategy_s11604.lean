import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_of_possemidef_det_ne_zero_2
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_succ_det_ne_zero
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_succ_possemidef

namespace Problems.LinearAlgebra.sylvester_criterion

-- Schur-complement upgrade, factored into: M PosSemidef, M.det ≠ 0, and the
-- generic upgrade lemma (PosSemidef + det ≠ 0 ⇒ PosDef). The upgrade is
-- re-declared as our own sub-goal (a proven sibling exists but lives in another
-- strategy module and is not auto-imported; Tier-1 dedup aliases this to it).
-- PosSemidef carries the (n×n block PosDef ⇒ Schur ≥ 0) argument; det ≠ 0 is the
-- top leading minor being positive. Both strictly weaker than the parent PosDef goal.
theorem s11604 {n : ℕ}
    (ih : ∀ (M : Matrix (Fin n) (Fin n) ℝ), M.IsHermitian →
      (∀ (k : Fin n), 0 < leadingPrincipalMinor M k) → M.PosDef)
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.PosDef  := by
  have hPSD : M.PosSemidef := posdef_succ_possemidef ih M hHerm hMinors
  have hdet : M.det ≠ 0 := posdef_succ_det_ne_zero M hMinors
  exact posdef_of_possemidef_det_ne_zero_2 hPSD hdet

end Problems.LinearAlgebra.sylvester_criterion
