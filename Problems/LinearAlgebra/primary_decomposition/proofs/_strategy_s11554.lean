import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_finset_factorization
import Problems.LinearAlgebra.primary_decomposition.proofs.L_fin_of_finset

namespace Problems.LinearAlgebra.primary_decomposition

-- Factor f as a finite product over a Finset of distinct monic irreducibles
-- (`finset_factorization`), then reindex that Finset to `Fin n` preserving every
-- predicate (`fin_of_finset`). The Finset version carries all the UFD math; the
-- reindexing is pure bookkeeping via `Finset.equivFin`.
theorem s11554 {K : Type*} [Field K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∃ (n : ℕ) (p : Fin n → Polynomial K) (e : Fin n → ℕ),
      (∀ i, Irreducible (p i)) ∧ (∀ i, (p i).Monic) ∧ (∀ i, 0 < e i) ∧
      Function.Injective p ∧
      (∀ i j, i ≠ j → IsCoprime (p i) (p j)) ∧
      f = ∏ i, (p i) ^ (e i)  := by
  obtain ⟨s, e, h1, h2, h3, h4, h5⟩ := finset_factorization f hf hf0
  exact fin_of_finset f s e h1 h2 h3 h4 h5

end Problems.LinearAlgebra.primary_decomposition
