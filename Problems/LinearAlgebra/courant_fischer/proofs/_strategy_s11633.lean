import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_orthobasis_repr_vanish_outside_span

namespace Problems.LinearAlgebra.courant_fischer

-- For x in the span of an orthonormal sub-family, the repr-components at
-- indices outside that family vanish — pure orthonormality, independent of T.
-- Reduce the concrete top-(k+1) eigenvector span to the abstract lemma:
-- predicate P j := (j:ℕ) ≤ k, and ¬P i follows from k < i.
theorem s11633
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}))
    (x : E) (hxS : x ∈ S) :
    ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0  := by
  intro i hi
  have hx : x ∈ Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {j : Fin n | (j : ℕ) ≤ (k : ℕ)}) := hS ▸ hxS
  exact orthobasis_repr_vanish_outside_span (hT.eigenvectorBasis hn)
      (fun j => (j : ℕ) ≤ (k : ℕ)) x hx i (not_le.mpr hi)

end Problems.LinearAlgebra.courant_fischer
