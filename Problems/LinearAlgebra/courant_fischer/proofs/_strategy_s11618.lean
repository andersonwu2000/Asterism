import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_exists_vector_rayleigh_le_eigenvalue
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_set_bddbelow

namespace Problems.LinearAlgebra.courant_fischer

-- Courant–Fischer upper bound (per fixed (k+1)-dim S): the inner Rayleigh sInf ≤ λ_k.
-- A dimension count yields a nonzero x ∈ S landing in the bottom eigenspace with
-- Rayleigh ≤ λ_k (h_exists); since that Rayleigh value lies in the bounded-below set
-- (h_bdd), csInf_le + transitivity closes the goal. Both sub-goals drop the sInf layer.
theorem s11618
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (S : Submodule ℝ E)
    (hScard : Module.finrank ℝ S = (k : ℕ) + 1) :
    sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2) ≤ hT.eigenvalues hn k  := by
  have h_exists := exists_vector_rayleigh_le_eigenvalue hT hn k S hScard
  have h_bdd := rayleigh_set_bddbelow hT S
  obtain ⟨x, hxS, hx0, hxle⟩ := h_exists
  exact le_trans (csInf_le h_bdd ⟨x, hxS, hx0, rfl⟩) hxle

end Problems.LinearAlgebra.courant_fischer
