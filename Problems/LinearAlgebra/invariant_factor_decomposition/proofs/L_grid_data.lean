-- Build the invariant-factor grid in two independent moves + one arithmetic leaf.
-- distinct_primes: enumerate the distinct monic irreducible primes q with a column key,
--   giving monic/irreducible/pairwise-coprime and p i = q (key i) (monic ⇒ rep is p i).
-- sorted_grid: pure-ℕ sorting/padding — places each positive exponent e i into row idx,
--   ascending grid c, injective idx over the positive-exponent subtype, padding zeros,
--   and every row has a positive entry (tallest column fills all rows).
-- row_nonunit: a row product of irreducible powers with one positive exponent is no unit.
-- Closer: assemble; cond 6 collapses to Associated.refl after rewriting key/value equalities.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11579

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def grid_data := @Problems.LinearAlgebra.invariant_factor_decomposition.s11579

end Problems.LinearAlgebra.invariant_factor_decomposition
