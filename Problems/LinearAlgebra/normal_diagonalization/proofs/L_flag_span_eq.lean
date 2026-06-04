-- Direct: Gram-Schmidt preserves each initial-segment span. Rewrite the orthonormal
-- basis vectors to `gramSchmidtNormed b` (they agree since `b` is linearly independent,
-- so `gramSchmidtNormed` is never zero), then chain mathlib's `span_gramSchmidtNormed`
-- (normed ↦ unnormalized) and `span_gramSchmidt_Iic` (Gram-Schmidt ↦ original) on `Iic j`.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11547

namespace Problems.LinearAlgebra.normal_diagonalization

def flag_span_eq := @Problems.LinearAlgebra.normal_diagonalization.s11547

end Problems.LinearAlgebra.normal_diagonalization
