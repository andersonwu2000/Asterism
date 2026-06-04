-- Direct leaf proof: the flag subspace `span (b '' Iic j)` is T-invariant.
-- Reduce `span ≤ comap T span` to its generators (`Submodule.span_le`); each
-- generator `b k` (k ≤ j) satisfies `T (b k) ∈ span (b '' Iic k) ⊆ span (b '' Iic j)`
-- via the adapted hypothesis `hb` + span/image/Iic monotonicity. No sub-goals.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11546

namespace Problems.LinearAlgebra.normal_diagonalization

def flag_invariant := @Problems.LinearAlgebra.normal_diagonalization.s11546

end Problems.LinearAlgebra.normal_diagonalization
