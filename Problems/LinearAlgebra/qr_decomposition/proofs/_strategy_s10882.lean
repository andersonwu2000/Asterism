import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs.L_columns_lin_indep_of_det_ne_zero
import Problems.LinearAlgebra.qr_decomposition.proofs.L_orthogonal_upper_triangularizer_of_lin_indep_columns

namespace Problems.LinearAlgebra.qr_decomposition

-- Reduce orthogonal-upper-triangularizer existence to two independent pieces:
--   (a) `A.det ≠ 0` lifts to linear independence of A's columns (`A.transpose`);
--   (b) any A with linearly-independent columns admits the orthogonal Q with
--       upper-triangular `Qᵀ * A` (the Gram-Schmidt-driven core).
-- Combinator just threads (a) into (b).
theorem s10882 : ∀ {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ),
    A.det ≠ 0 →
    ∃ Q : Matrix (Fin n) (Fin n) ℝ,
      Q * Matrix.transpose Q = 1 ∧ (Matrix.transpose Q * A).BlockTriangular id  := by
  intro n A hA
  have h_li : LinearIndependent ℝ A.transpose :=
    columns_lin_indep_of_det_ne_zero A hA
  exact orthogonal_upper_triangularizer_of_lin_indep_columns A h_li

end Problems.LinearAlgebra.qr_decomposition
