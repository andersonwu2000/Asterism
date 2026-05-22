-- Reduce to building a flag-adapted basis (pure linear algebra, no T): a basis b
-- with span(b '' Set.Iic j) = W (j.val + 1). T-invariance of W (j.val + 1) then
-- transports T (b j) into that span, since b j ∈ W (j.val + 1).
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10836

namespace Problems.LinearAlgebra.schur_triangularization

def adapted_basis_of_flag := @Problems.LinearAlgebra.schur_triangularization.s10836

end Problems.LinearAlgebra.schur_triangularization
