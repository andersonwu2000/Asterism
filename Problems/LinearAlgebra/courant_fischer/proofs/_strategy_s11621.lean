import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_exists_test_subspace_inf_ge_eigenvalue
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_sup_set_bdd_above

namespace Problems.LinearAlgebra.courant_fischer

-- Lower bound λ_k ≤ sSup via `le_csSup` with the top-(k+1)-eigenvector test subspace.
-- h_bdd (rayleigh_sup_set_bdd_above): the sSup set is bounded above (each member sInf
--   ≤ ‖T‖ by Cauchy–Schwarz), giving the `BddAbove` premise of `le_csSup`.
-- h_exists (exists_test_subspace_inf_ge_eigenvalue): a witness subspace S of finrank k+1
--   whose Rayleigh sInf is ≥ λ_k; it is a member of the sSup set, so λ_k ≤ sInf S ≤ sSup.
theorem s11621
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    hT.eigenvalues hn k ≤
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2))  := by
  have h_bdd := rayleigh_sup_set_bdd_above hT hn k
  have h_exists := exists_test_subspace_inf_ge_eigenvalue hT hn k
  obtain ⟨S, hS, hge⟩ := h_exists
  exact le_trans hge (le_csSup h_bdd ⟨S, hS, rfl⟩)

end Problems.LinearAlgebra.courant_fischer
