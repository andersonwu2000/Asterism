import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_ge_on_topeig
import Problems.LinearAlgebra.courant_fischer.proofs.L_topeig_set_nonempty
import Problems.LinearAlgebra.courant_fischer.proofs.L_topeig_subspace_finrank

namespace Problems.LinearAlgebra.courant_fischer

-- Witness subspace S = span of the top (k+1) eigenvectors {e_0,…,e_k}.
-- Three sub-goals: (1) finrank S = k+1; (2) the Rayleigh set is nonempty;
-- (3) every nonzero x ∈ S has Rayleigh ≥ λ_k (heart: λ_i ≥ λ_k for i ≤ k by
-- antitone, expand numerator in the eigenbasis).  Then le_csInf glues (2)+(3)
-- into λ_k ≤ sInf, and S, (1) discharge the existential.
theorem s11623
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ S : Submodule ℝ E,
      Module.finrank ℝ S = (k : ℕ) + 1 ∧
      hT.eigenvalues hn k ≤ sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
        q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)  := by
  refine ⟨Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}), ?_, ?_⟩
  · exact topeig_subspace_finrank hT hn k _ rfl
  · apply le_csInf
    · exact topeig_set_nonempty hT hn k _ rfl
    · rintro q ⟨x, hxS, hx0, rfl⟩
      exact rayleigh_ge_on_topeig hT hn k _ rfl x hxS hx0

end Problems.LinearAlgebra.courant_fischer
