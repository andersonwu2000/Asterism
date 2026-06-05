import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- exists_nonzero_mem_of_finrank_pos: a submodule of positive finrank contains a nonzero element
-- Uses S ≠ ⊥ (from finrank > 0) and Submodule.exists_mem_ne_zero_of_ne_bot.
theorem exists_nonzero_mem_of_finrank_pos
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E]
    (S : Submodule ℝ E) (m : ℕ) (h : Module.finrank ℝ S = m + 1) :
    ∃ x ∈ S, x ≠ 0 := by
  have hne : S ≠ ⊥ := by
    intro heq
    have : Module.finrank ℝ S = 0 := heq ▸ finrank_bot ℝ E
    omega
  exact Submodule.exists_mem_ne_zero_of_ne_bot hne

end Problems.LinearAlgebra.courant_fischer
