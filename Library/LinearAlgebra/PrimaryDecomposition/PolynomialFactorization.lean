import Library.LinearAlgebra.PrimaryDecomposition.NormalizedFactors
import Mathlib

open Library.LinearAlgebra.PrimaryDecomposition.NormalizedFactors

namespace Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization

-- Reindex the Finset `s` of distinct monic irreducibles to `Fin s.card` via `s.equivFin`.
-- Witness: n = s.card, p i = ↑(s.equivFin.symm i), e' i = e (p i). Each predicate transfers
-- from membership `(s.equivFin.symm i).property`; injectivity/coprimality use that the
-- composite `val ∘ equivFin.symm` is injective; the product equality is `Equiv.prod_comp`
-- over the attach reindexing of `s`. Pure bookkeeping — closes directly, no sub-goals.
theorem fin_of_finset {K : Type*} [Field K] (f : Polynomial K)
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

-- Witness the Finset as `(normalizedFactors f).toFinset` and exponents as multiset
-- `count`. The five conjuncts split into independent UFD facts about membership of
-- `normalizedFactors`: each member is irreducible / monic (FieldDivision's
-- `mem_normalizedFactors_iff`), its count is positive (toFinset membership), distinct
-- members are coprime (distinct monic irreducibles), and the finset-power product
-- recovers `f` (monic ⇒ leading coeff 1, so the normalized-factor product is exactly f).
-- `classical` supplies `DecidableEq K`, giving the `NormalizationMonoid`/`toFinset`
-- instances the locked `[Field K]` signature lacks. Each sub-goal re-derives it via `[DecidableEq K]`.
theorem finset_factorization {K : Type*} [Field K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∃ (s : Finset (Polynomial K)) (e : Polynomial K → ℕ),
      (∀ p ∈ s, Irreducible p) ∧ (∀ p ∈ s, p.Monic) ∧ (∀ p ∈ s, 0 < e p) ∧
      (∀ p ∈ s, ∀ q ∈ s, p ≠ q → IsCoprime p q) ∧
      f = ∏ p ∈ s, p ^ (e p)  := by
  classical
  refine ⟨(UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      fun p => (UniqueFactorizationMonoid.normalizedFactors f).count p, ?_, ?_, ?_, ?_, ?_⟩
  · have h1 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, Irreducible p :=
      nf_mem_irreducible f hf hf0
    exact h1
  · have h2 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p.Monic :=
      nf_mem_monic f hf hf0
    exact h2
  · have h3 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        0 < (UniqueFactorizationMonoid.normalizedFactors f).count p :=
      nf_mem_count_pos f hf hf0
    exact h3
  · have h4 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        ∀ q ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p ≠ q → IsCoprime p q :=
      nf_mem_pairwise_coprime f hf hf0
    exact h4
  · have h5 : f = ∏ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        p ^ (UniqueFactorizationMonoid.normalizedFactors f).count p :=
      nf_prod_pow_count f hf hf0
    exact h5

-- Factor f as a finite product over a Finset of distinct monic irreducibles
-- (`finset_factorization`), then reindex that Finset to `Fin n` preserving every
-- predicate (`fin_of_finset`). The Finset version carries all the UFD math; the
-- reindexing is pure bookkeeping via `Finset.equivFin`.
theorem exists_finpow_factorization {K : Type*} [Field K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∃ (n : ℕ) (p : Fin n → Polynomial K) (e : Fin n → ℕ),
      (∀ i, Irreducible (p i)) ∧ (∀ i, (p i).Monic) ∧ (∀ i, 0 < e i) ∧
      Function.Injective p ∧
      (∀ i j, i ≠ j → IsCoprime (p i) (p j)) ∧
      f = ∏ i, (p i) ^ (e i)  := by
  obtain ⟨s, e, h1, h2, h3, h4, h5⟩ := finset_factorization f hf hf0
  exact fin_of_finset f s e h1 h2 h3 h4 h5

end Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization
