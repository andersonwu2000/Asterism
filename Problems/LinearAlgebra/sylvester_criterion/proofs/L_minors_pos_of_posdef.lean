import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- minors_pos_of_posdef: PosDef.submatrix + PosDef.det_pos closes each leading minor directly.
-- Each leading k-block is a submatrix via Fin.castLE (injective), so PosDef.submatrix applies;
-- PosDef.det_pos then gives the positive determinant = leadingPrincipalMinor.
theorem minors_pos_of_posdef {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) :
    M.PosDef → ∀ k : Fin n, 0 < leadingPrincipalMinor M k := by
  intro hM k
  unfold leadingPrincipalMinor
  simp only
  have hk : k.val + 1 ≤ n := by have := k.isLt; omega
  have hinj : Function.Injective (Fin.castLE hk) := Fin.castLE_injective hk
  exact (hM.submatrix hinj).det_pos

end Problems.LinearAlgebra.sylvester_criterion
