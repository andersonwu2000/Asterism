import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- flag_seq_choose_step: packages pointwise Classical.choose of hext into v : Fin d → V
theorem flag_seq_choose_step :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          W j.val ⊔ Submodule.span K {v j} = W (j.val + 1) := by
  intro K _ V _ _ _ W _h0 _hmono _hrank hext
  exact ⟨fun j => Classical.choose (hext j.val j.isLt),
         fun j => (Classical.choose_spec (hext j.val j.isLt)).2⟩

end Problems.LinearAlgebra.schur_triangularization
