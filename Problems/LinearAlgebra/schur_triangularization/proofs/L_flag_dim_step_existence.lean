import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- entry_kind: Builder
-- flag_dim_step_existence: finrank inequality forces W(j+1) ⊋ U
theorem flag_dim_step_existence :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∀ (j : ℕ), j < Module.finrank K V →
      ∀ (U : Submodule K V), U ≤ W (j + 1) → Module.finrank K U = j →
      ∃ v, v ∈ W (j + 1) ∧ v ∉ U := by
  intro K _instK V _instAG _instMod _instFD W _hW0 _hMono hrank j hj U hU hUrank
  -- finrank K (W (j+1)) = j+1 since j < finrank K V
  have hrankWj1 : Module.finrank K (W (j + 1)) = j + 1 := by
    rw [hrank (j + 1)]
    simp [Nat.min_eq_left (Nat.succ_le_of_lt hj)]
  -- U ≠ W(j+1) because their ranks differ
  have hne : U ≠ W (j + 1) := by
    intro heq
    rw [heq] at hUrank
    omega
  -- U ⊊ W(j+1)
  have hslt : U < W (j + 1) := lt_of_le_of_ne hU hne
  exact (SetLike.exists_of_lt hslt)

end Problems.LinearAlgebra.schur_triangularization
