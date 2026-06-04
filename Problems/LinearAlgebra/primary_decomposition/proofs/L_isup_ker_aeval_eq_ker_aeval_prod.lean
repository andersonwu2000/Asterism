-- n-factor coprime kernel-decomposition: ⨆ ker(aeval T qᵢ) = ker(aeval T ∏qᵢ).
-- Split by `le_antisymm` into the two inclusions:
--   • h_le : ⨆ ≤ ker(prod) — pure divisibility (qᵢ ∣ ∏), no coprimality needed;
--   • h_ge : ker(prod) ≤ ⨆ — the coprime n-factor induction (uses hcop).
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11558

namespace Problems.LinearAlgebra.primary_decomposition

def isup_ker_aeval_eq_ker_aeval_prod := @Problems.LinearAlgebra.primary_decomposition.s11558

end Problems.LinearAlgebra.primary_decomposition
