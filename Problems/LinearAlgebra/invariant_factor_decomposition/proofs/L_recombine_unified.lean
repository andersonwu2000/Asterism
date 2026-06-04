-- Recombine prime-power summands into an invariant-factor grid in two moves.
-- h_regroup: construct the grid (distinct monic primes q, ascending exponent grid c,
--   pairwise-coprime q) plus the K[X]-linear iso onto the *double* sum ⨁ₖ⨁ₜ K[X]/(qₜ^cₖₜ)
--   — the witness-bearing crux, but with each summand an individual prime power.
-- h_crt: collapse each column ⨁ₜ K[X]/(qₜ^cₖₜ) ≃ K[X]/(∏ₜ qₜ^cₖₜ) via fibre-wise CRT.
-- Closer: chain the two isos; the arithmetic conditions pass straight through.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11572

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def recombine_unified := @Problems.LinearAlgebra.invariant_factor_decomposition.s11572

end Problems.LinearAlgebra.invariant_factor_decomposition
