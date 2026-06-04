import Mathlib

namespace Problems.LinearAlgebra.rational_canonical_form

/-- Companion matrix of a polynomial `f` (used at monic `f` of positive
degree). The `f.natDegree × f.natDegree` matrix with `1`'s on the
subdiagonal and the negated coefficients of `f` in the last column —
i.e. the matrix of "multiplication by `x`" on `K[X]/(f)` in the basis
`1, x, …, x^{natDegree-1}`. -/
def companionMatrix {K : Type*} [Field K] (f : Polynomial K) :
    Matrix (Fin f.natDegree) (Fin f.natDegree) K :=
  Matrix.of fun i j =>
    if (i : ℕ) = (j : ℕ) + 1 then 1
    else if (j : ℕ) = f.natDegree - 1 then -f.coeff (i : ℕ)
    else 0

end Problems.LinearAlgebra.rational_canonical_form
