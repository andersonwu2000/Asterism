import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_set_bddbelow

namespace Problems.LinearAlgebra.courant_fischer

theorem rayleigh_bddbelow_for_subspace
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    (S : Submodule ℝ E) :
    BddBelow (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2) := by apply rayleigh_set_bddbelow <;> assumption

end Problems.LinearAlgebra.courant_fischer
