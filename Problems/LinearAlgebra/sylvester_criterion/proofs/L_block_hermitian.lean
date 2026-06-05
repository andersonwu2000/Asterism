import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- block_hermitian: IsHermitian is preserved by submatrix; toBlocks₁₁ is Sum.inl submatrix
theorem block_hermitian {n : ℕ} (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.IsHermitian := by
  simp only [Matrix.toBlocks₁₁]
  exact hHerm.submatrix (↑finSumFinEquiv ∘ Sum.inl)

end Problems.LinearAlgebra.sylvester_criterion
