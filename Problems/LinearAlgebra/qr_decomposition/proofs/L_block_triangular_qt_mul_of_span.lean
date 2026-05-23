-- Block-triangularity reduces to entry-wise vanishing for j < i.
--   (1) qt_mul_entry_eq_inner: rewrites the (i,j) entry of Qᵀ * A as the inner
--       product ⟨q i, A's j-th column⟩ — purely a sum-vs-inner identity.
--   (2) orthonormal_inner_span_iic_zero: orthonormality of q makes q i orthogonal
--       to span ℝ (q '' Set.Iic j) whenever j < i; the column lies in that span.
-- Combinator: intro i j (j < i); chain the two equalities to 0.
import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs._strategy_s10884

namespace Problems.LinearAlgebra.qr_decomposition

def block_triangular_qt_mul_of_span := @Problems.LinearAlgebra.qr_decomposition.s10884

end Problems.LinearAlgebra.qr_decomposition
