import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs.L_exists_orthonormal_triangular_span_of_li
import Problems.LinearAlgebra.qr_decomposition.proofs.L_li_columns_in_euclidean_space

namespace Problems.LinearAlgebra.qr_decomposition

-- Reduce to Gram-Schmidt on LI vectors in EuclideanSpace:
--   (1) transport LI of A.transpose through (EuclideanSpace.equiv).symm,
--   (2) Gram-Schmidt existence (orthonormal q with triangular span) for any
--       LI family in EuclideanSpace ℝ (Fin n) — the actual content.
-- Combinator: forward both sub-goals; the witness from (2) is exactly the
-- existential the parent asks for, with v := (Eucl.equiv).symm ∘ A.transpose.
theorem s10885 {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) :
    LinearIndependent ℝ A.transpose →
    ∃ q : Fin n → EuclideanSpace ℝ (Fin n),
      Orthonormal ℝ q ∧
        ∀ i : Fin n,
          (EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose i) ∈
            Submodule.span ℝ (q '' Set.Iic i)  := by
  intro hLI
  have h_eucl_li :
      LinearIndependent ℝ
        (fun i : Fin n => (EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose i)) :=
    li_columns_in_euclidean_space A hLI
  exact exists_orthonormal_triangular_span_of_li A _ h_eucl_li

end Problems.LinearAlgebra.qr_decomposition
