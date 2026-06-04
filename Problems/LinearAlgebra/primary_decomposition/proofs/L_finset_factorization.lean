-- Witness the Finset as `(normalizedFactors f).toFinset` and exponents as multiset
-- `count`. The five conjuncts split into independent UFD facts about membership of
-- `normalizedFactors`: each member is irreducible / monic (FieldDivision's
-- `mem_normalizedFactors_iff`), its count is positive (toFinset membership), distinct
-- members are coprime (distinct monic irreducibles), and the finset-power product
-- recovers `f` (monic ⇒ leading coeff 1, so the normalized-factor product is exactly f).
-- `classical` supplies `DecidableEq K`, giving the `NormalizationMonoid`/`toFinset`
-- instances the locked `[Field K]` signature lacks. Each sub-goal re-derives it via `[DecidableEq K]`.
import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs._strategy_s11557

namespace Problems.LinearAlgebra.primary_decomposition

def finset_factorization := @Problems.LinearAlgebra.primary_decomposition.s11557

end Problems.LinearAlgebra.primary_decomposition
