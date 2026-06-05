import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_eigenvalue_le_sup_inf_rayleigh
import Problems.LinearAlgebra.courant_fischer.proofs.L_sup_inf_rayleigh_le_eigenvalue

namespace Problems.LinearAlgebra.courant_fischer

-- Courant–Fischer max-min equality, proved by `le_antisymm` over two bounds.
-- h_lower (sub-goal A): eigenvalue k ≤ sSup, via the top-(k+1)-eigenvector test
--   subspace S₀ where every Rayleigh quotient ≥ eigenvalue k.
-- h_upper (sub-goal B): sSup ≤ eigenvalue k, via any (k+1)-dim S meeting the
--   bottom-(n−k)-eigenvector subspace in a nonzero x with Rayleigh ≤ eigenvalue k.
-- Each bound is a standalone theorem re-declaring all binders; both rely on the
-- proved bricks rayleigh_numerator_eigenbasis / subspace_inter_nonzero_of_finrank.
theorem s11615 : ∀ {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n),
    hT.eigenvalues hn k =
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2))  := by
  intro E _ _ _ T hT n hn k
  have h_lower : hT.eigenvalues hn k ≤
      sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) :=
    eigenvalue_le_sup_inf_rayleigh hT hn k
  have h_upper : sSup (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
        Module.finrank ℝ S = (k : ℕ) + 1 ∧
        r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
          q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)) ≤ hT.eigenvalues hn k :=
    sup_inf_rayleigh_le_eigenvalue hT hn k
  exact le_antisymm h_lower h_upper

end Problems.LinearAlgebra.courant_fischer
