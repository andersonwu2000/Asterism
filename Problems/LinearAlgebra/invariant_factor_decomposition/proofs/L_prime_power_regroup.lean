-- Regroup prime-power summands into the invariant-factor grid in two separable moves.
-- grid_data: pure combinatorics/arithmetic — distinct monic primes q, ascending exponent
--   grid c (pairwise-coprime, non-unit columns) PLUS an injective reindexing
--   idx : {i // 0 < e i} → Fin r × Fin s matching each pᵢ^eᵢ to its grid cell (over the
--   POSITIVE-exponent subtype, fixing s11574's e i = 0 counterexample) with off-image
--   cells padded to exponent 0.  No module theory.
-- reindex_iso: the witness-INDEPENDENT module iso, fed the reindexing data (idx, hinj,
--   hassoc, hpad) explicitly so it can biject support summands and drop trivial ones
--   (this is what s11574's data-less `directsum_reindex_padded` lacked when it shelved).
-- Closer: the four arithmetic conditions pass straight through; the iso is reindex_iso.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11577

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def prime_power_regroup := @Problems.LinearAlgebra.invariant_factor_decomposition.s11577

end Problems.LinearAlgebra.invariant_factor_decomposition
