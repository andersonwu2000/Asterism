-- Drop the subsingleton (¬P) summands: the inclusion {i//P i} ↪ I induces a linear
-- equivalence because every dropped summand M i is a subsingleton (hence 0).
-- F restricts a sum to its P-components, G includes the subtype components back; the
-- two round-trips close componentwise (toModule_lof), the ¬P case via Subsingleton.elim.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11586

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def drop_subsingleton_subtype := @Problems.LinearAlgebra.invariant_factor_decomposition.s11586

end Problems.LinearAlgebra.invariant_factor_decomposition
