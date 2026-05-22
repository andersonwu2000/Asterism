import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- flag_step_extends_span: for each step n < finrank K V, W(n+1) = W(n) ⊔ span K {vnext}
-- for some vnext ∈ W(n+1); apply the step-existence hypothesis with U := W n, then close
-- W(n+1) ≤ W(n) ⊔ span K {vnext} via equal finrank + containment.
theorem flag_step_extends_span :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ (j : ℕ), j < Module.finrank K V →
        ∀ (U : Submodule K V), U ≤ W (j + 1) → Module.finrank K U = j →
        ∃ v, v ∈ W (j + 1) ∧ v ∉ U) →
      ∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1) := by
  intro K _ V _ _ _ W _hW0 hWmono hWrank hstep n hn
  have hrank_n : Module.finrank K (W n) = n := by
    have := hWrank n
    simp [Nat.min_eq_left (Nat.le_of_lt hn)] at this
    exact this
  have hn_step : W n ≤ W (n + 1) := hWmono n
  obtain ⟨vnext, hvnext_mem, hvnext_notin⟩ := hstep n hn (W n) hn_step hrank_n
  refine ⟨vnext, hvnext_mem, ?_⟩
  apply le_antisymm
  · apply sup_le hn_step
    exact Submodule.span_le.mpr (Set.singleton_subset_iff.mpr hvnext_mem)
  · have hrank_sup : Module.finrank K ((W n ⊔ Submodule.span K {vnext} : Submodule K V)) =
        n + 1 := by
      rw [Submodule.finrank_sup_span_singleton hvnext_notin, hrank_n]
    have hrank_next : Module.finrank K (W (n + 1)) = n + 1 := by
      have := hWrank (n + 1)
      simp [Nat.min_eq_left hn] at this
      exact this
    have hle : W n ⊔ Submodule.span K {vnext} ≤ W (n + 1) := by
      apply sup_le hn_step
      exact Submodule.span_le.mpr (Set.singleton_subset_iff.mpr hvnext_mem)
    exact (Submodule.eq_of_le_of_finrank_eq hle (hrank_sup.trans hrank_next.symm)).symm.le

end Problems.LinearAlgebra.schur_triangularization
