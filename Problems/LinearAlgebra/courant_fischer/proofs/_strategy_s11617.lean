import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_exists_subspace_finrank
import Problems.LinearAlgebra.courant_fischer.proofs.L_inf_rayleigh_le_eigenvalue

namespace Problems.LinearAlgebra.courant_fischer

-- Courant–Fischer upper bound: sSup over (k+1)-dim subspaces of the inner sInf
-- Rayleigh quotient is ≤ eigenvalue k. Closed by `csSup_le`:
--   • h_exists (exists_subspace_finrank): the index set is nonempty — some (k+1)-dim
--     subspace exists, so the sSup has a witness `r`.
--   • h_inf (inf_rayleigh_le_eigenvalue): for EVERY (k+1)-dim S, the inner sInf of the
--     Rayleigh set is ≤ eigenvalue k (dimension count yields a nonzero vector in
--     S meeting the bottom-(n−k) eigenspace, whose Rayleigh quotient is ≤ λ_k).
-- Both sub-goals drop the outer sSup layer, hence are strictly simpler.
theorem s11617
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) ≤ hT.eigenvalues hn k  := by
  have h_exists := exists_subspace_finrank hn k
  have h_inf := fun (S : Submodule ℝ E) (hS : Module.finrank ℝ S = (k : ℕ) + 1) =>
    inf_rayleigh_le_eigenvalue hT hn k S hS
  apply csSup_le
  · obtain ⟨S, hS⟩ := h_exists
    exact ⟨_, S, hS, rfl⟩
  · rintro r ⟨S, hScard, rfl⟩
    exact h_inf S hScard

end Problems.LinearAlgebra.courant_fischer
