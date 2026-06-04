-- Recombine prime-power cyclic summands into an invariant-factor (divisibility) chain.
-- `recombine_unified` (Backward, the crux): produces the column grid — distinct monic
--   primes `q`, an exponent grid `c` non-decreasing along columns — and the K[X]-linear
--   iso onto `⨁ K[X]/(∏ₜ q t ^ c k t)`; this is the witness-bearing existence kept unified.
-- `divchain_column_products` (Builder, witness-independent): column products with
--   per-prime non-decreasing exponents form a divisibility chain.
-- Closer: take f k := ∏ₜ q t ^ c k t; monic from `monic_prod_of_monic`/`Monic.pow`,
--   non-unit from the grid, divisibility from `divchain_column_products`, iso direct.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11571

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def recombine_invariant_factors := @Problems.LinearAlgebra.invariant_factor_decomposition.s11571

end Problems.LinearAlgebra.invariant_factor_decomposition
