import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_block_conjtranspose
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_leading_block_posdef
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_schur_complement_possemidef

namespace Problems.LinearAlgebra.sylvester_criterion

-- Schur-complement induction step: M (size n+1) is PosSemidef. Reindex via
-- `finSumFinEquiv` into 2×2 blocks, then `PosDef.fromBlocks₁₁` reduces PosSemidef
-- of the whole to PosSemidef of the Schur complement. Three strictly-simpler pieces:
--   • leading_block_posdef     — the top-left n×n block is PosDef (uses `ih`);
--   • block_conjtranspose      — Hermitian symmetry of the off-diagonal blocks;
--   • schur_complement_possemidef — the 1-dim Schur complement is PosSemidef.
theorem s11605 {n : ℕ}
    (ih : ∀ (M : Matrix (Fin n) (Fin n) ℝ), M.IsHermitian →
      (∀ (k : Fin n), 0 < leadingPrincipalMinor M k) → M.PosDef)
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.PosSemidef  := by
  classical
  rw [← Matrix.posSemidef_submatrix_equiv (finSumFinEquiv (m := n) (n := 1))]
  have hApd : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.PosDef :=
    leading_block_posdef ih M hHerm hMinors
  letI : Invertible (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ := hApd.isUnit.invertible
  have hC := block_conjtranspose M hHerm
  rw [← Matrix.fromBlocks_toBlocks (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))), hC,
      Matrix.PosDef.fromBlocks₁₁ _ _ hApd]
  exact schur_complement_possemidef M hHerm hMinors hApd

end Problems.LinearAlgebra.sylvester_criterion
