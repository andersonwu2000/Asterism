import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_isup_ker_aeval_le_ker_aeval_prod
import Problems.LinearAlgebra.primary_decomposition.proofs.L_ker_aeval_prod_le_isup_ker_aeval

namespace Problems.LinearAlgebra.primary_decomposition

-- n-factor coprime kernel-decomposition: ⨆ ker(aeval T qᵢ) = ker(aeval T ∏qᵢ).
-- Split by `le_antisymm` into the two inclusions:
--   • h_le : ⨆ ≤ ker(prod) — pure divisibility (qᵢ ∣ ∏), no coprimality needed;
--   • h_ge : ker(prod) ≤ ⨆ — the coprime n-factor induction (uses hcop).
theorem s11558
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) {n : ℕ} (q : Fin n → Polynomial K)
    (hcop : Pairwise (fun i j => IsCoprime (q i) (q j))) :
    ⨆ i, LinearMap.ker (Polynomial.aeval T (q i)) = LinearMap.ker (Polynomial.aeval T (∏ i, q i))  := by
  apply le_antisymm
  · exact isup_ker_aeval_le_ker_aeval_prod T q
  · exact ker_aeval_prod_le_isup_ker_aeval T q hcop

end Problems.LinearAlgebra.primary_decomposition
