import Mathlib

namespace Library.LinearAlgebra.NormalDiagonalization.Flag

-- Direct leaf proof: the flag subspace `span (b '' Iic j)` is T-invariant.
-- Reduce `span ≤ comap T span` to its generators (`Submodule.span_le`); each
-- generator `b k` (k ≤ j) satisfies `T (b k) ∈ span (b '' Iic k) ⊆ span (b '' Iic j)`
-- via the adapted hypothesis `hb` + span/image/Iic monotonicity. No sub-goals.
theorem flag_invariant {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V)
    (b : Module.Basis (Fin (Module.finrank ℂ V)) ℂ V)
    (hb : ∀ j : Fin (Module.finrank ℂ V),
        T (b j) ∈ Submodule.span ℂ (b '' Set.Iic j))
    (j : Fin (Module.finrank ℂ V)) (v : V)
    (hv : v ∈ Submodule.span ℂ (b '' Set.Iic j)) :
    T v ∈ Submodule.span ℂ (b '' Set.Iic j)  := by
  have key : Submodule.span ℂ (b '' Set.Iic j) ≤
      (Submodule.span ℂ (b '' Set.Iic j)).comap T := by
    rw [Submodule.span_le]
    rintro _ ⟨k, hk, rfl⟩
    simp only [Submodule.mem_comap, SetLike.mem_coe]
    exact Submodule.span_mono (Set.image_mono (Set.Iic_subset_Iic.mpr hk)) (hb k)
  exact key hv

-- Direct: Gram-Schmidt preserves each initial-segment span. Rewrite the orthonormal
-- basis vectors to `gramSchmidtNormed b` (they agree since `b` is linearly independent,
-- so `gramSchmidtNormed` is never zero), then chain mathlib's `span_gramSchmidtNormed`
-- (normed ↦ unnormalized) and `span_gramSchmidt_Iic` (Gram-Schmidt ↦ original) on `Iic j`.
theorem flag_span_eq {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
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

end Library.LinearAlgebra.NormalDiagonalization.Flag
