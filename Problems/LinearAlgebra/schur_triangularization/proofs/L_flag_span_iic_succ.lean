import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- entry_kind: Builder
-- flag_span_iic_succ: Set.Iic decomposition + span_union + IH advances W(n+1) to W(n+2)
-- Splits Iic ⟨n+1,_⟩ = Iic ⟨n,_⟩ ∪ {⟨n+1,_⟩}, applies span_union, rewrites by IH, closes
-- with the chain hypothesis hchain at index ⟨n+1, hn⟩.
theorem flag_span_iic_succ :
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
      ∀ (n : ℕ) (hn : n + 1 < Module.finrank K V),
        Submodule.span K (v '' Set.Iic (⟨n, Nat.lt_of_succ_lt hn⟩ :
            Fin (Module.finrank K V))) = W (n + 1) →
        Submodule.span K (v '' Set.Iic (⟨n + 1, hn⟩ : Fin (Module.finrank K V)))
    = W (n + 2) := by
  intro K _ V _ _ _ W v _ _ _ _ hchain n hn IH
  have hn' := Nat.lt_of_succ_lt hn
  have hIic : Set.Iic (⟨n + 1, hn⟩ : Fin (Module.finrank K V)) =
      Set.Iic (⟨n, hn'⟩ : Fin (Module.finrank K V)) ∪ {⟨n + 1, hn⟩} := by
    ext ⟨k, hk⟩
    simp only [Set.mem_Iic, Set.mem_union, Set.mem_singleton_iff,
               Fin.mk_le_mk, Fin.mk.injEq]
    omega
  rw [hIic, Set.image_union, Set.image_singleton, Submodule.span_union, IH]
  exact hchain ⟨n + 1, hn⟩
end Problems.LinearAlgebra.schur_triangularization
