-- K[X]-linear Chinese Remainder iso, proved directly (leaf, no sub-goals).
-- Cite mathlib's ring-level CRT `Ideal.quotientInfRingEquivPiQuotient` (coprimality of
-- the principal ideals from `Ideal.isCoprime_span_singleton_iff` on `hg`), then upgrade
-- that `≃+*` to `≃ₗ[K[X]]` by supplying `map_smul'`: on a representative `mk a` both
-- sides reduce to `fun i => mk (r * a)`, so `rfl` after `ext i`.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11569

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def crt_quot_inf_pi := @Problems.LinearAlgebra.invariant_factor_decomposition.s11569

end Problems.LinearAlgebra.invariant_factor_decomposition
