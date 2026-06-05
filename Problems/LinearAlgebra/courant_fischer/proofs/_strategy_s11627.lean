import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_numerator_ge_eigenvalue
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_components_vanish

namespace Problems.LinearAlgebra.courant_fischer

-- For x in the top-(k+1) eigenvector span S, the Rayleigh quotient ≥ λ_k.
-- Decouple into: (1) components of x outside the top (k+1) eigendirections
-- vanish (pure geometry of S); (2) with those vanishing, the eigenbasis
-- expansion gives the numerator bound λ_k·‖x‖² ≤ ⟪Tx,x⟫ (antitone spectrum).
-- Divide by ‖x‖² > 0 (x ≠ 0) to close.
theorem s11627
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}))
    (x : E) (hxS : x ∈ S) (hx0 : x ≠ 0) :
    hT.eigenvalues hn k ≤ @inner ℝ E _ (T x) x / ‖x‖ ^ 2  := by
  have hpos : (0:ℝ) < ‖x‖ ^ 2 := pow_pos (norm_pos_iff.mpr hx0) 2
  have hv := rayleigh_components_vanish hT hn k S hS x hxS
  have hnum := numerator_ge_eigenvalue hT hn k x hv
  exact (le_div_iff₀ hpos).mpr hnum

end Problems.LinearAlgebra.courant_fischer
