import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_bottom_eigenspace_with_support
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_le_of_low_modes_zero

namespace Problems.LinearAlgebra.courant_fischer

-- Construct the bottom (n−k)-eigenvector subspace W and bound its Rayleigh quotient.
-- bottom_eigenspace_with_support: ∃ W, finrank W = n−k whose vectors have all
--   "high" eigen-modes < k vanishing (⟪eᵢ, x⟫ = 0 for i < k) — the construction half.
-- rayleigh_le_of_low_modes_zero: any x with those modes zero has Rayleigh ≤ λ_k via
--   the eigenbasis expansion + eigenvalue antitonicity — the spectral half, W-free.
-- Combine: pull W from the first, feed its support property into the second pointwise.
theorem s11622
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ W : Submodule ℝ E, Module.finrank ℝ W = n - (k : ℕ) ∧
      ∀ x : E, x ∈ W → x ≠ 0 →
        @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  obtain ⟨W, hWrank, hWsupp⟩ := bottom_eigenspace_with_support hT hn k
  exact ⟨W, hWrank, fun x hxW hx0 =>
    rayleigh_le_of_low_modes_zero hT hn k x hx0 (hWsupp x hxW)⟩

end Problems.LinearAlgebra.courant_fischer
