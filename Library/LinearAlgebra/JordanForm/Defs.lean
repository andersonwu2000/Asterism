import Mathlib

namespace Library.LinearAlgebra.JordanForm.Defs

def IsJordanForm {n : ℕ} {K : Type*} [Field K]
    (M : Matrix (Fin n) (Fin n) K) : Prop :=
  ∀ i j : Fin n,
    if (i : ℕ) = (j : ℕ) then True
    else if (i : ℕ) + 1 = (j : ℕ) then M i j = 0 ∨ (M i j = 1 ∧ M i i = M j j)
    else M i j = 0

end Library.LinearAlgebra.JordanForm.Defs
