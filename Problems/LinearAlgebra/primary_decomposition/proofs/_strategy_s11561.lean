import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_ker_aeval_le_of_dvd

namespace Problems.LinearAlgebra.primary_decomposition

-- ⨆ ker(aeval T qᵢ) ≤ ker(aeval T ∏qⱼ): pure divisibility, no coprimality.
-- iSup_le reduces to a per-factor inclusion; each qᵢ ∣ ∏qⱼ (Finset.dvd_prod_of_mem),
-- and ker(aeval T ·) is monotone under polynomial divisibility (ker_aeval_le_of_dvd).
theorem s11561
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K) :
    ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) ≤
      LinearMap.ker (Polynomial.aeval T (∏ i, q i))  := by
  apply iSup_le
  intro i
  have hdvd : q i ∣ ∏ j, q j := Finset.dvd_prod_of_mem q (Finset.mem_univ i)
  exact ker_aeval_le_of_dvd T (q i) (∏ j, q j) hdvd

end Problems.LinearAlgebra.primary_decomposition
