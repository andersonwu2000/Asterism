import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- A PosSemidef matrix with nonzero determinant is PosDef, via the eigenvalue criterion.
-- PosDef ↔ all eigenvalues > 0; each eigenvalue is ≥ 0 (PosSemidef), and none is 0 since
-- det = ∏ eigenvalues ≠ 0 (a zero eigenvalue would force the product to vanish).
theorem s11601 {n : Type*} [Fintype n] [DecidableEq n]
    {M : Matrix n n ℝ} (hM : M.PosSemidef) (hd : M.det ≠ 0) : M.PosDef := by
  rw [hM.isHermitian.posDef_iff_eigenvalues_pos]
  intro i
  refine lt_of_le_of_ne (hM.eigenvalues_nonneg i) (Ne.symm ?_)
  intro h0
  apply hd
  rw [hM.isHermitian.det_eq_prod_eigenvalues]
  exact Finset.prod_eq_zero (Finset.mem_univ i) (by simp [← h0])

end Problems.LinearAlgebra.sylvester_criterion
