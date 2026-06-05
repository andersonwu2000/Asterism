import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_bottom_eigenspace_exists
import Problems.LinearAlgebra.courant_fischer.proofs.L_subspace_inter_nonzero

namespace Problems.LinearAlgebra.courant_fischer

-- Courant–Fischer upper bound: a nonzero x ∈ S with Rayleigh ≤ λ_k exists.
-- h_bottom (sub-goal): the bottom (n−k)-eigenvector subspace W has finrank n−k and
--   every nonzero vector in it has Rayleigh ≤ λ_k (the spectral content; drops S).
-- subspace_inter_nonzero (sub-goal, dedupes to the proved dimension-count brick):
--   finrank S + finrank W = (k+1)+(n−k) = n+1 > n forces a nonzero x ∈ S ⊓ W.
-- Combining, that x lies in W so hWbound bounds its Rayleigh by λ_k.
theorem s11619
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (S : Submodule ℝ E)
    (hScard : Module.finrank ℝ S = (k : ℕ) + 1) :
    ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  have hk := k.isLt
  obtain ⟨W, hWdim, hWbound⟩ := bottom_eigenspace_exists hT hn k
  obtain ⟨x, hxS, hxW, hx0⟩ :=
    subspace_inter_nonzero S W hn (by omega)
  exact ⟨x, hxS, hx0, hWbound x hxW hx0⟩



end Problems.LinearAlgebra.courant_fischer
