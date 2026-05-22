-- Pick witness U' := U ⊔ span {v}. Inclusion U ≤ U' is `le_sup_left`.
-- Sub-goal (a) `sup_span_singleton_invariant`: T-invariance of U' uses hTU and
-- `T v - μ • v ∈ U` to land `T v = μ • v + (T v - μ • v)` back in U'.
-- Sub-goal (b) `sup_span_singleton_finrank`: rank jumps by one because v ∉ U.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10842

namespace Problems.LinearAlgebra.schur_triangularization

def extend_via_near_eigenvector := @Problems.LinearAlgebra.schur_triangularization.s10842

end Problems.LinearAlgebra.schur_triangularization
