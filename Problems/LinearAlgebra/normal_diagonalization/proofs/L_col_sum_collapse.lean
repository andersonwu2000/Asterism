import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs

namespace Problems.LinearAlgebra.normal_diagonalization

-- col_sum_collapse: column i's squared-norm sum collapses to ‖M i i‖²
-- because htri kills entries above row i and ih kills entries below row i in column i.
theorem col_sum_collapse {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id) (i : Fin n)
    (ih : ∀ j : Fin n, j < i → ∀ k : Fin n, j ≠ k → M j k = 0) :
    ∑ k, ‖M k i‖ ^ 2 = ‖M i i‖ ^ 2 := by
  apply Finset.sum_eq_single i
  · intro k _ hki
    rcases lt_or_gt_of_ne hki with hlt | hgt
    · have h0 : M k i = 0 := ih k hlt i hki
      simp [h0]
    · have h0 : M k i = 0 := htri hgt
      simp [h0]
  · intro hi
    exact absurd (Finset.mem_univ i) hi

end Problems.LinearAlgebra.normal_diagonalization
