import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- exists_nonzero_mem_inf_of_finrank: dimension-count intersection over a general field
-- If dim U + dim W > dim V, then U ⊓ W contains a nonzero vector.
theorem exists_nonzero_mem_inf_of_finrank {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (U W : Submodule K V)
    (h : Module.finrank K V < Module.finrank K U + Module.finrank K W) :
    ∃ x : V, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by
  have hinf_pos : 0 < Module.finrank K (U ⊓ W : Submodule K V) := by
    have hsup_le : Module.finrank K (U ⊔ W : Submodule K V) ≤ Module.finrank K V :=
      Submodule.finrank_le _
    have heq := Submodule.finrank_sup_add_finrank_inf_eq U W
    omega
  have hinf_ne_bot : (U ⊓ W : Submodule K V) ≠ ⊥ := by
    intro heq
    rw [heq, finrank_bot] at hinf_pos
    exact Nat.lt_irrefl 0 hinf_pos
  obtain ⟨x, hxmem, hxne⟩ := Submodule.exists_mem_ne_zero_of_ne_bot hinf_ne_bot
  exact ⟨x, hxmem.1, hxmem.2, hxne⟩

end Problems.LinearAlgebra.eckart_young
