import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs

namespace Problems.LinearAlgebra.normal_diagonalization

-- Direct: Gram-Schmidt preserves each initial-segment span. Rewrite the orthonormal
-- basis vectors to `gramSchmidtNormed b` (they agree since `b` is linearly independent,
-- so `gramSchmidtNormed` is never zero), then chain mathlib's `span_gramSchmidtNormed`
-- (normed ↦ unnormalized) and `span_gramSchmidt_Iic` (Gram-Schmidt ↦ original) on `Iic j`.
theorem s11547 {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V]
    (b : Module.Basis (Fin (Module.finrank ℂ V)) ℂ V)
    (hcard : Module.finrank ℂ V = Fintype.card (Fin (Module.finrank ℂ V)))
    (j : Fin (Module.finrank ℂ V)) :
    Submodule.span ℂ
        ((InnerProductSpace.gramSchmidtOrthonormalBasis hcard b).toBasis '' Set.Iic j)
      = Submodule.span ℂ (b '' Set.Iic j)  := by
  have hne : ∀ i, InnerProductSpace.gramSchmidtNormed ℂ b i ≠ 0 := by
    intro i
    have : ‖InnerProductSpace.gramSchmidtNormed ℂ b i‖ = 1 :=
      InnerProductSpace.gramSchmidtNormed_unit_length i b.linearIndependent
    intro h
    rw [h, norm_zero] at this
    norm_num at this
  have hfun : (InnerProductSpace.gramSchmidtOrthonormalBasis hcard b).toBasis '' Set.Iic j
      = InnerProductSpace.gramSchmidtNormed ℂ b '' Set.Iic j := by
    apply Set.image_congr'
    intro i
    rw [OrthonormalBasis.coe_toBasis]
    exact InnerProductSpace.gramSchmidtOrthonormalBasis_apply hcard (hne i)
  rw [hfun, InnerProductSpace.span_gramSchmidtNormed, InnerProductSpace.span_gramSchmidt_Iic]

end Problems.LinearAlgebra.normal_diagonalization
