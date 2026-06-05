import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_topeig_eigenbasis_linindep_on_set
import Problems.LinearAlgebra.courant_fischer.proofs.L_topeig_le_subtype_card

namespace Problems.LinearAlgebra.courant_fischer

-- S = span of the top (k+1) eigenvectors; finrank = #generators since they are independent.
-- hA: the eigenvectorBasis vectors over the index set {i ≤ k} are linearly independent
--     (so the span's dimension equals the number of generators);
-- hB: that index set has exactly k+1 elements.
-- Combine: rewrite the image as a range, apply finrank_span_eq_card hA, close with hB.
theorem s11629
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)})) :
    Module.finrank ℝ S = (k : ℕ) + 1  := by
  have hA : LinearIndependent ℝ
      (fun i : ↥{i : Fin n | (i : ℕ) ≤ (k : ℕ)} => (hT.eigenvectorBasis hn) (i : Fin n)) :=
    topeig_eigenbasis_linindep_on_set hT hn k
  have hB : Fintype.card {i : Fin n // (i : ℕ) ≤ (k : ℕ)} = (k : ℕ) + 1 :=
    topeig_le_subtype_card k
  rw [hS, Set.image_eq_range, finrank_span_eq_card hA]
  exact hB

end Problems.LinearAlgebra.courant_fischer
