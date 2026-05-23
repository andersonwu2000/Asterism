import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs.L_orthonormal_inner_span_iic_zero
import Problems.LinearAlgebra.qr_decomposition.proofs.L_qt_mul_entry_eq_inner

namespace Problems.LinearAlgebra.qr_decomposition

-- Block-triangularity reduces to entry-wise vanishing for j < i.
--   (1) qt_mul_entry_eq_inner: rewrites the (i,j) entry of Qᵀ * A as the inner
--       product ⟨q i, A's j-th column⟩ — purely a sum-vs-inner identity.
--   (2) orthonormal_inner_span_iic_zero: orthonormality of q makes q i orthogonal
--       to span ℝ (q '' Set.Iic j) whenever j < i; the column lies in that span.
-- Combinator: intro i j (j < i); chain the two equalities to 0.
theorem s10884 {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ)
    (q : Fin n → EuclideanSpace ℝ (Fin n)) :
    Orthonormal ℝ q →
    (∀ i : Fin n,
      (EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose i) ∈
        Submodule.span ℝ (q '' Set.Iic i)) →
    ((Matrix.of fun i j => q j i).transpose * A).BlockTriangular id  := by
  intro h_ortho h_span i j hij
  have h_qt_entry := qt_mul_entry_eq_inner A q i j
  have h_inner_zero :=
    orthonormal_inner_span_iic_zero q i j
      ((EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose j)) h_ortho (h_span j) hij
  exact h_qt_entry.trans h_inner_zero

end Problems.LinearAlgebra.qr_decomposition
