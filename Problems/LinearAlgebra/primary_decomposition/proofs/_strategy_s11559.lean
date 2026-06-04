import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_coprime_q_prod_erase
import Problems.LinearAlgebra.primary_decomposition.proofs.L_sup_ker_le_ker_prod

namespace Problems.LinearAlgebra.primary_decomposition

-- `iSupIndep` of the kernels reduces (via `iSupIndep_def`) to per-`i` disjointness
-- of `ker (aeval T (q i))` from the join of the others. The join is bounded above
-- by `ker (aeval T (∏_{j≠i} q j))` (h_le), and `q i` is coprime to that product
-- (h_cop, from pairwise coprimality); `disjoint_ker_aeval_of_isCoprime` + `mono_right`
-- then close it. Both sub-goals are single-`i` facts, strictly simpler than the n-fold
-- independence.
theorem s11559
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    iSupIndep (fun i => LinearMap.ker (Polynomial.aeval T (q i)))  := by
  rw [iSupIndep_def]
  intro i
  have h_le := sup_ker_le_ker_prod T q i
  have h_cop := coprime_q_prod_erase q hcop i
  exact (Polynomial.disjoint_ker_aeval_of_isCoprime T h_cop).mono_right h_le

end Problems.LinearAlgebra.primary_decomposition
