import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_subspace_inter_nonzero_of_finrank

namespace Problems.LinearAlgebra.courant_fischer

theorem subspace_inter_nonzero
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] (U W : Submodule ℝ E) {n : ℕ}
    (hn : Module.finrank ℝ E = n)
    (h : n < Module.finrank ℝ U + Module.finrank ℝ W) :
    ∃ x : E, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by apply subspace_inter_nonzero_of_finrank <;> assumption

end Problems.LinearAlgebra.courant_fischer
