-- ⨆ ker(aeval T qᵢ) ≤ ker(aeval T ∏qⱼ): pure divisibility, no coprimality.
-- iSup_le reduces to a per-factor inclusion; each qᵢ ∣ ∏qⱼ (Finset.dvd_prod_of_mem),
-- and ker(aeval T ·) is monotone under polynomial divisibility (ker_aeval_le_of_dvd).
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11561

namespace Problems.LinearAlgebra.primary_decomposition

def isup_ker_aeval_le_ker_aeval_prod := @Problems.LinearAlgebra.primary_decomposition.s11561

end Problems.LinearAlgebra.primary_decomposition
