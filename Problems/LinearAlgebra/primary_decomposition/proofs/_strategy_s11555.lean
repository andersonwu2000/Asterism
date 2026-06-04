import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_isup_ker_aeval_eq_ker_aeval_prod
import Problems.LinearAlgebra.primary_decomposition.proofs.L_ker_aeval_isupindep_of_pairwise_coprime

namespace Problems.LinearAlgebra.primary_decomposition

-- Internal-direct-sum decomposition V = ⊕ ker(aeval T (q i)) for pairwise
-- coprime qᵢ, reduced via `isInternal_submodule_of_iSupIndep_of_iSup_eq_top`
-- to its two premises:
--   • h_indep : the kernels are `iSupIndep` (n-factor independence built from
--     pairwise coprimality of the qᵢ);
--   • h_sup   : their join equals ker(aeval T (∏ qᵢ)) (n-factor coprime
--     kernel-decomposition), which is ⊤ by `htop`.
-- Both sub-goals are strictly simpler n-factor inductions; the parent is then
-- a pure two-premise assembly via the combinator.
theorem s11555
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j)))
    (htop : LinearMap.ker (Polynomial.aeval T (∏ i, q i)) = ⊤) :
    DirectSum.IsInternal (fun i => LinearMap.ker (Polynomial.aeval T (q i)))  := by
  have h_indep : iSupIndep (fun i => LinearMap.ker (Polynomial.aeval T (q i))) :=
    ker_aeval_isupindep_of_pairwise_coprime T q hcop
  have h_sup : ⨆ i, LinearMap.ker (Polynomial.aeval T (q i))
      = LinearMap.ker (Polynomial.aeval T (∏ i, q i)) :=
    isup_ker_aeval_eq_ker_aeval_prod T q hcop
  exact DirectSum.isInternal_submodule_of_iSupIndep_of_iSup_eq_top h_indep (h_sup.trans htop)

end Problems.LinearAlgebra.primary_decomposition
