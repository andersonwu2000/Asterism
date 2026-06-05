import Mathlib

namespace Problems.LinearAlgebra.sylvester_criterion

/-- The `k`-th **leading principal minor** of `M`: the determinant of the
top-left `(k+1) × (k+1)` block (rows and columns `0 … k`). The inclusion
`Fin (k+1) ↪ Fin n` is the canonical `Fin.castLE`. -/
def leadingPrincipalMinor {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) (k : Fin n) : ℝ :=
  let incl : Fin (k.val + 1) → Fin n := Fin.castLE (by have := k.isLt; omega)
  (M.submatrix incl incl).det

end Problems.LinearAlgebra.sylvester_criterion
