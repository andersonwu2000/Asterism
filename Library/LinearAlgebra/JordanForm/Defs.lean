import Mathlib

namespace Library.LinearAlgebra.JordanForm

/-- A matrix is in Jordan normal form iff:
- diagonal entries are arbitrary (the eigenvalues, each repeated by algebraic multiplicity),
- super-diagonal entries are `0` or `1`, with `1` allowed only when both adjacent diagonal
  entries agree (i.e. within a Jordan block of a single eigenvalue),
- all other entries are `0`.

Vacuously true on the empty matrix (`n = 0`). For `n = 1` only the diagonal entry exists,
so the predicate accepts any value (single-block Jordan form). -/
def IsJordanForm {n : ℕ} {K : Type*} [Field K]
    (M : Matrix (Fin n) (Fin n) K) : Prop :=
  ∀ i j : Fin n,
    if (i : ℕ) = (j : ℕ) then True
    else if (i : ℕ) + 1 = (j : ℕ) then M i j = 0 ∨ (M i j = 1 ∧ M i i = M j j)
    else M i j = 0

end Library.LinearAlgebra.JordanForm
