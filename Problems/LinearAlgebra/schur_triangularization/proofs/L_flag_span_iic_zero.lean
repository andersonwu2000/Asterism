import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- flag_span_iic_zero: base case j=0 of span-equals-flag using Set.Iic singleton + bot_sup_eq
-- entry_kind: Builder
theorem flag_span_iic_zero :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V)
      (v : Fin (Module.finrank K V) → V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      (∀ j : Fin (Module.finrank K V),
        W j.val ⊔ Submodule.span K {v j} = W (j.val + 1)) →
      ∀ (h : 0 < Module.finrank K V),
        Submodule.span K (v '' Set.Iic (⟨0, h⟩ : Fin (Module.finrank K V))) = W 1 := by
  intro K _ V _ _ _ W v hW0 _ _ _ hchain h
  have hIic : Set.Iic (⟨0, h⟩ : Fin (Module.finrank K V)) = {⟨0, h⟩} := by
    ext j; simp [Set.mem_Iic, Set.mem_singleton_iff, Fin.ext_iff, Fin.le_def]
  rw [hIic, Set.image_singleton]
  have hstep := hchain ⟨0, h⟩
  simp only [Nat.zero_add] at hstep
  rw [hW0] at hstep
  simp only [bot_sup_eq] at hstep
  exact hstep
end Problems.LinearAlgebra.schur_triangularization
