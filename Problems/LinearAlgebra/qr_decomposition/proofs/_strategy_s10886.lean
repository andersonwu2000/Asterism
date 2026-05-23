import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs

namespace Problems.LinearAlgebra.qr_decomposition

-- Direct closure via mathlib's Gram-Schmidt: witness q := gramSchmidtNormed ℝ v.
-- Orthonormality: gramSchmidtNormed_orthonormal hv. Triangular span: rewrite
-- span(q '' Iic i) through span_gramSchmidtNormed → span_gramSchmidt_Iic to
-- reduce to span(v '' Iic i), where v i ∈ span via subset_span.
theorem s10886 {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ)
    (v : Fin n → EuclideanSpace ℝ (Fin n)) :
    LinearIndependent ℝ v →
    ∃ q : Fin n → EuclideanSpace ℝ (Fin n),
      Orthonormal ℝ q ∧
        ∀ i : Fin n, v i ∈ Submodule.span ℝ (q '' Set.Iic i)  := by
  intro hv
  refine ⟨InnerProductSpace.gramSchmidtNormed ℝ v, ?_, ?_⟩
  · exact InnerProductSpace.gramSchmidtNormed_orthonormal hv
  · intro i
    have h1 : Submodule.span ℝ (InnerProductSpace.gramSchmidtNormed ℝ v '' Set.Iic i)
            = Submodule.span ℝ (InnerProductSpace.gramSchmidt ℝ v '' Set.Iic i) :=
      InnerProductSpace.span_gramSchmidtNormed v (Set.Iic i)
    have h2 : Submodule.span ℝ (InnerProductSpace.gramSchmidt ℝ v '' Set.Iic i)
            = Submodule.span ℝ (v '' Set.Iic i) :=
      InnerProductSpace.span_gramSchmidt_Iic ℝ v i
    rw [h1, h2]
    exact Submodule.subset_span ⟨i, Set.self_mem_Iic, rfl⟩

end Problems.LinearAlgebra.qr_decomposition