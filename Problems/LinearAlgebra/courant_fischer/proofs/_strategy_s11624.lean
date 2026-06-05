import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_exists_nonzero_mem_of_finrank_pos
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_bddbelow_for_subspace
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_le_bound

namespace Problems.LinearAlgebra.courant_fischer

-- BddAbove of the outer Courant–Fischer set {sInf(Rayleigh S) : finrank S = k+1}.
-- Upper bound = C, where ‖T x‖ ≤ C‖x‖ (operator bound, cited inline via toContinuousLinearMap).
-- For each S: exists_nonzero_mem_of_finrank_pos gives a nonzero x ∈ S (finrank = k+1 > 0);
-- rayleigh_le_bound bounds its Rayleigh quotient ≤ C; rayleigh_bddbelow_for_subspace gives
-- BddBelow, so csInf_le_of_le pushes sInf(Rayleigh S) ≤ (that quotient) ≤ C.
theorem s11624
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    BddAbove (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
      Module.finrank ℝ S = (k : ℕ) + 1 ∧
      r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
        q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2))  := by
  obtain ⟨C, hC⟩ : ∃ C : ℝ, ∀ x : E, ‖T x‖ ≤ C * ‖x‖ :=
    ⟨‖LinearMap.toContinuousLinearMap T‖, fun x => (LinearMap.toContinuousLinearMap T).le_opNorm x⟩
  refine ⟨C, ?_⟩
  rintro r ⟨S, hScard, rfl⟩
  obtain ⟨x, hxS, hx0⟩ := exists_nonzero_mem_of_finrank_pos S (k : ℕ) hScard
  exact csInf_le_of_le (rayleigh_bddbelow_for_subspace hT S)
    ⟨x, hxS, hx0, rfl⟩ (rayleigh_le_bound T C hC x hx0)

end Problems.LinearAlgebra.courant_fischer
