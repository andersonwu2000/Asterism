import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_card_fin_subtype_ge
import Problems.LinearAlgebra.courant_fischer.proofs.L_linear_independent_basis_subset

namespace Problems.LinearAlgebra.courant_fischer

-- Span of an orthonormal-basis subset has finrank = cardinality of the index set.
-- hLI: the restricted family {b i : m ≤ i} is linearly independent (orthonormal ⇒ indep).
-- hcard: there are n − m indices i : Fin n with m ≤ i.
-- Rewrite the image as a range, then `finrank_span_eq_card` turns the goal into the count.
theorem s11630
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E) (m : ℕ) :
    Module.finrank ℝ (Submodule.span ℝ (b '' {i : Fin n | m ≤ (i : ℕ)})) = n - m  := by
  have hLI : LinearIndependent ℝ (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) :=
    linear_independent_basis_subset b m
  have hcard : Fintype.card {i : Fin n // m ≤ (i : ℕ)} = n - m :=
    card_fin_subtype_ge n m
  have himg : b '' {i : Fin n | m ≤ (i : ℕ)}
      = Set.range (fun i : {i : Fin n // m ≤ (i : ℕ)} => b (i : Fin n)) :=
    Set.image_eq_range _ _
  rw [himg, finrank_span_eq_card hLI, hcard]

end Problems.LinearAlgebra.courant_fischer
