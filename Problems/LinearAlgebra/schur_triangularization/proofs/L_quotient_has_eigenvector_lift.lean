-- Split the quotient-eigenvector lift into (A) `Nontrivial (V ⧸ U)` from the finrank gap,
-- (B) algebraic-closedness gives the induced endomorphism on `V ⧸ U` an eigenvalue with a
-- nonzero quotient witness, and (C) pure quotient algebra translates any such witness
-- back to `v ∉ U` together with `T v - μ • v ∈ U`. Only (B) uses `IsAlgClosed`.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10843

namespace Problems.LinearAlgebra.schur_triangularization

def quotient_has_eigenvector_lift := @Problems.LinearAlgebra.schur_triangularization.s10843

end Problems.LinearAlgebra.schur_triangularization
