import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_minors_pos_of_posdef
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_of_minors_pos

namespace Problems.LinearAlgebra.sylvester_criterion

-- Sylvester's criterion: split the iff into its two implications.
-- Forward (`minors_pos_of_posdef`): each leading block is a PosDef submatrix, so its
-- determinant (= the leading minor) is positive — short, no induction.
-- Reverse (`posdef_of_minors_pos`): induction on n via Schur complement, upgrading
-- PosSemidef to PosDef using the proved sibling. Iff.intro recombines them.
theorem s11602 : ∀ {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ),
    M.IsHermitian →
    (M.PosDef ↔ ∀ k : Fin n, 0 < leadingPrincipalMinor M k)  := by
  intro n M hHerm
  exact Iff.intro (minors_pos_of_posdef M) (posdef_of_minors_pos M hHerm)

end Problems.LinearAlgebra.sylvester_criterion
