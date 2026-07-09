import Mathlib

/-!
# Flag subspaces for normal diagonalization

This file establishes two supporting lemmas about the initial-segment spans
`Submodule.span ℂ (b '' Set.Iic j)` formed by an ordered basis `b`.  Together
they show that these spans form a T-invariant flag and that replacing `b` by the
associated Gram–Schmidt orthonormal basis leaves each flag subspace unchanged.
-/

namespace Library.LinearAlgebra.NormalDiagonalization.Flag

variable {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V] [FiniteDimensional ℂ V]

/-- The initial-segment span `Submodule.span ℂ (b '' Set.Iic j)` is invariant under `T`,
provided each basis vector `b k` maps into `Submodule.span ℂ (b '' Set.Iic k)`. -/
theorem flag_invariant (T : V →ₗ[ℂ] V)
    (b : Module.Basis (Fin (Module.finrank ℂ V)) ℂ V)
    (hb : ∀ j : Fin (Module.finrank ℂ V),
        T (b j) ∈ Submodule.span ℂ (b '' Set.Iic j))
    (j : Fin (Module.finrank ℂ V)) (v : V)
    (hv : v ∈ Submodule.span ℂ (b '' Set.Iic j)) :
    T v ∈ Submodule.span ℂ (b '' Set.Iic j) := by
  have key : Submodule.span ℂ (b '' Set.Iic j) ≤
      (Submodule.span ℂ (b '' Set.Iic j)).comap T := by
    rw [Submodule.span_le]
    rintro _ ⟨k, hk, rfl⟩
    simp only [Submodule.mem_comap, SetLike.mem_coe]
    exact Submodule.span_mono (Set.image_mono (Set.Iic_subset_Iic.mpr hk)) (hb k)
  exact key hv

/-- The initial-segment span of the Gram–Schmidt orthonormal basis vectors equals the
initial-segment span of the original basis: `span (gramSchmidtOrthonormalBasis '' Iic j) = span (b '' Iic j)`. -/
theorem flag_span_eq
    (b : Module.Basis (Fin (Module.finrank ℂ V)) ℂ V)
    (hcard : Module.finrank ℂ V = Fintype.card (Fin (Module.finrank ℂ V)))
    (j : Fin (Module.finrank ℂ V)) :
    Submodule.span ℂ
        ((InnerProductSpace.gramSchmidtOrthonormalBasis hcard b).toBasis '' Set.Iic j)
      = Submodule.span ℂ (b '' Set.Iic j) := by
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

end Library.LinearAlgebra.NormalDiagonalization.Flag
