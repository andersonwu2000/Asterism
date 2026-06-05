import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- Each leading block-minor equals a leading minor of M, hence positive.
-- The top-left n×n block B = M.submatrix (castAdd 1) (castAdd 1); its leading
-- (k+1)-minor reindexes to M's leading minor at k.castSucc (val-preserving Fin
-- maps coincide), so `congr 1` after unfolding closes the equality; positivity
-- then follows from hMinors at k.castSucc. No sub-goals needed.
theorem s11608 {n : ℕ} (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    ∀ (k : Fin n), 0 < leadingPrincipalMinor
      (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ k  := by
  intro k
  have h_minor_eq : leadingPrincipalMinor
      (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ k
      = leadingPrincipalMinor M k.castSucc := by
    simp only [leadingPrincipalMinor, Matrix.toBlocks₁₁]
    congr 1
  rw [h_minor_eq]
  exact hMinors k.castSucc

end Problems.LinearAlgebra.sylvester_criterion
