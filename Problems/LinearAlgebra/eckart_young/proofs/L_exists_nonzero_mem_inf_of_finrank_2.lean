import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_nonzero_mem_inf_of_finrank

namespace Problems.LinearAlgebra.eckart_young

theorem exists_nonzero_mem_inf_of_finrank_2 {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (U W : Submodule K V)
    (h : Module.finrank K V < Module.finrank K U + Module.finrank K W) :
    ∃ x : V, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by apply exists_nonzero_mem_inf_of_finrank <;> assumption

end Problems.LinearAlgebra.eckart_young
