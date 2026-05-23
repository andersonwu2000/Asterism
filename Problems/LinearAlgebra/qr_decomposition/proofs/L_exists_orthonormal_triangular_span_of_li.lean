-- Direct closure via mathlib's Gram-Schmidt: witness q := gramSchmidtNormed ℝ v.
-- Orthonormality: gramSchmidtNormed_orthonormal hv. Triangular span: rewrite
-- span(q '' Iic i) through span_gramSchmidtNormed → span_gramSchmidt_Iic to
-- reduce to span(v '' Iic i), where v i ∈ span via subset_span.
import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs._strategy_s10886

namespace Problems.LinearAlgebra.qr_decomposition

def exists_orthonormal_triangular_span_of_li := @Problems.LinearAlgebra.qr_decomposition.s10886

end Problems.LinearAlgebra.qr_decomposition
