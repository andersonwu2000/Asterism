import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- Reindex the Finset `s` of distinct monic irreducibles to `Fin s.card` via `s.equivFin`.
-- Witness: n = s.card, p i = ↑(s.equivFin.symm i), e' i = e (p i). Each predicate transfers
-- from membership `(s.equivFin.symm i).property`; injectivity/coprimality use that the
-- composite `val ∘ equivFin.symm` is injective; the product equality is `Equiv.prod_comp`
-- over the attach reindexing of `s`. Pure bookkeeping — closes directly, no sub-goals.
theorem s11556 {K : Type*} [Field K] (f : Polynomial K)
    (s : Finset (Polynomial K)) (e : Polynomial K → ℕ)
    (h1 : ∀ p ∈ s, Irreducible p) (h2 : ∀ p ∈ s, p.Monic) (h3 : ∀ p ∈ s, 0 < e p)
    (h4 : ∀ p ∈ s, ∀ q ∈ s, p ≠ q → IsCoprime p q)
    (h5 : f = ∏ p ∈ s, p ^ (e p)) :
    ∃ (n : ℕ) (p : Fin n → Polynomial K) (e' : Fin n → ℕ),
      (∀ i, Irreducible (p i)) ∧ (∀ i, (p i).Monic) ∧ (∀ i, 0 < e' i) ∧
      Function.Injective p ∧
      (∀ i j, i ≠ j → IsCoprime (p i) (p j)) ∧
      f = ∏ i, (p i) ^ (e' i)  := by
  set g := s.equivFin.symm
  refine ⟨s.card, fun i => ↑(g i), fun i => e ↑(g i),
    fun i => h1 _ (g i).property, fun i => h2 _ (g i).property,
    fun i => h3 _ (g i).property, ?_, ?_, ?_⟩
  · exact fun i j h => g.injective (Subtype.coe_injective h)
  · intro i j hij
    refine h4 _ (g i).property _ (g j).property ?_
    exact fun h => hij (g.injective (Subtype.coe_injective h))
  · rw [h5, ← Finset.prod_attach s (fun p => p ^ e p)]
    exact (Equiv.prod_comp g (fun x : {x // x ∈ s} => (↑x : Polynomial K) ^ e ↑x)).symm



end Problems.LinearAlgebra.primary_decomposition
