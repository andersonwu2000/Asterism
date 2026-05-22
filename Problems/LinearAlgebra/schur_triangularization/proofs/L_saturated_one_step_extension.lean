import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- entry_kind: Builder
-- saturated_one_step_extension: wraps one-step extension hypothesis to saturate at finrank V
theorem saturated_one_step_extension :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        Module.finrank K U < Module.finrank K V →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = Module.finrank K U + 1) →
      ∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V) := by
  intro K _ V _ _ _ T h_ext U hU
  by_cases h : Module.finrank K U < Module.finrank K V
  · obtain ⟨U', hle, hinv, hrank⟩ := h_ext U hU h
    exact ⟨U', hle, hinv, by rw [hrank, Nat.min_eq_left h]⟩
  · have h' : Module.finrank K V ≤ Module.finrank K U := Nat.le_of_not_lt h
    have heq : Module.finrank K U = Module.finrank K V :=
      Nat.le_antisymm (Submodule.finrank_le U) h'
    exact ⟨U, le_refl _, hU, by rw [heq, min_eq_right (Nat.le_succ _)]⟩

end Problems.LinearAlgebra.schur_triangularization
