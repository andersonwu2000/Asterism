import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- coprime_q_prod_erase: IsCoprime q i with product over erase i, from pairwise coprimality
-- Uses IsCoprime.prod_right_iff to reduce to per-factor coprimality, then hcop.
theorem coprime_q_prod_erase
    {K : Type*} [Field K] {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) (i : Fin n) :
    IsCoprime (q i) (∏ j ∈ Finset.univ.erase i, q j) := by
  rw [IsCoprime.prod_right_iff]
  intro j hj
  exact hcop ((Finset.mem_erase.mp hj).1).symm
end Problems.LinearAlgebra.primary_decomposition
