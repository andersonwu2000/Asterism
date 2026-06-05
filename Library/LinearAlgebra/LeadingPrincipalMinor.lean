import Mathlib

namespace Library.LinearAlgebra.LeadingPrincipalMinor

def leadingPrincipalMinor {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) (k : Fin n) : ℝ :=
  let incl : Fin (k.val + 1) → Fin n := Fin.castLE (by have := k.isLt; omega)
  (M.submatrix incl incl).det

end Library.LinearAlgebra.LeadingPrincipalMinor
