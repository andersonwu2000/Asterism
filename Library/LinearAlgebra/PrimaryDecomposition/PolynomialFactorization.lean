import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.Polynomial.FieldDivision
import Mathlib.Data.Fintype.EquivFin
import Mathlib.Data.Multiset.Basic
import Mathlib.RingTheory.Coprime.Basic
import Mathlib.RingTheory.PrincipalIdealDomain
import Mathlib.RingTheory.UniqueFactorizationDomain.NormalizedFactors

/-!
# Polynomial factorization into prime powers

This file provides lemmas about the unique factorization of monic nonzero polynomials
over a field into products of powers of distinct monic irreducibles.  The development
unpacks the abstract UFD structure from `UniqueFactorizationMonoid.normalizedFactors`
into a concrete `Finset`-indexed product, and then re-indexes that product over `Fin n`.

## Main statements

- `finset_factorization`: a monic nonzero polynomial over a field admits a
  `Finset`-indexed factorization into distinct monic irreducibles raised to positive
  integer powers.
- `exists_finpow_factorization`: the same factorization re-indexed over `Fin n`,
  together with injectivity of the factor map.
-/

namespace Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization

/-- Every element of the support `(normalizedFactors f).toFinset` appears with positive
multiplicity in the multiset `normalizedFactors f`. -/
theorem nf_mem_count_pos {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (_hf : f.Monic) (_hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      0 < (UniqueFactorizationMonoid.normalizedFactors f).count p := by
  intro p hp
  exact Multiset.count_pos.mpr (Multiset.mem_toFinset.mp hp)

/-- Every element of the support `(normalizedFactors f).toFinset` is irreducible. -/
theorem nf_mem_irreducible {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (_hf : f.Monic) (_hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, Irreducible p := by
  intro p hp
  rw [Multiset.mem_toFinset] at hp
  exact UniqueFactorizationMonoid.irreducible_of_normalized_factor p hp

/-- Every element of the support `(normalizedFactors f).toFinset` is monic. -/
theorem nf_mem_monic {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (_hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p.Monic := by
  intro p hp
  rw [Multiset.mem_toFinset] at hp
  exact ((Polynomial.mem_normalizedFactors_iff hf0).mp hp).2.1

/-- Distinct elements of the support `(normalizedFactors f).toFinset` are coprime. -/
theorem nf_mem_pairwise_coprime {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (_hf : f.Monic) (_hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      ∀ q ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        p ≠ q → IsCoprime p q := by
  intro p hp q hq hpq
  have hp' := Multiset.mem_toFinset.mp hp
  have hq' := Multiset.mem_toFinset.mp hq
  have hirp := UniqueFactorizationMonoid.irreducible_of_normalized_factor p hp'
  rw [hirp.coprime_iff_not_dvd]
  intro hdvd
  exact hpq (UniqueFactorizationMonoid.normalizedFactors_eq_of_dvd f p hp' q hq' hdvd)

/-- A monic nonzero polynomial equals the product over its normalized-factor support of each
factor raised to its multiplicity in `normalizedFactors f`. -/
theorem nf_prod_pow_count {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    f = ∏ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      p ^ (UniqueFactorizationMonoid.normalizedFactors f).count p := by
  conv_lhs => rw [← hf.normalize_eq_self,
    ← UniqueFactorizationMonoid.prod_normalizedFactors_eq hf0]
  exact Finset.prod_multiset_count _

/-- **Finset factorization**: a monic nonzero polynomial `f` over a field factors as
$f = \prod_{p \in s} p^{e(p)}$ where `s` is a `Finset` of distinct monic irreducibles
and `e : Polynomial K → ℕ` assigns each factor a positive exponent. -/
theorem finset_factorization {K : Type*} [Field K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∃ (s : Finset (Polynomial K)) (e : Polynomial K → ℕ),
      (∀ p ∈ s, Irreducible p) ∧ (∀ p ∈ s, p.Monic) ∧ (∀ p ∈ s, 0 < e p) ∧
      (∀ p ∈ s, ∀ q ∈ s, p ≠ q → IsCoprime p q) ∧
      f = ∏ p ∈ s, p ^ (e p) := by
  classical
  exact ⟨(UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      fun p => (UniqueFactorizationMonoid.normalizedFactors f).count p,
      nf_mem_irreducible f hf hf0,
      nf_mem_monic f hf hf0,
      nf_mem_count_pos f hf hf0,
      nf_mem_pairwise_coprime f hf hf0,
      nf_prod_pow_count f hf hf0⟩

/-- Re-indexes a `Finset`-indexed factorization of `f` to a `Fin n`-indexed one.
Given `h5 : f = ∏ p ∈ s, p ^ (e p)` with the usual conditions, produces an injective
family `p : Fin n → Polynomial K` and exponents `e' : Fin n → ℕ` such that
`f = ∏ i, (p i) ^ (e' i)`, via `Finset.equivFin`. -/
theorem fin_of_finset {K : Type*} [Field K] (f : Polynomial K)
    (s : Finset (Polynomial K)) (e : Polynomial K → ℕ)
    (h1 : ∀ p ∈ s, Irreducible p) (h2 : ∀ p ∈ s, p.Monic) (h3 : ∀ p ∈ s, 0 < e p)
    (h4 : ∀ p ∈ s, ∀ q ∈ s, p ≠ q → IsCoprime p q)
    (h5 : f = ∏ p ∈ s, p ^ (e p)) :
    ∃ (n : ℕ) (p : Fin n → Polynomial K) (e' : Fin n → ℕ),
      (∀ i, Irreducible (p i)) ∧ (∀ i, (p i).Monic) ∧ (∀ i, 0 < e' i) ∧
      Function.Injective p ∧
      (∀ i j, i ≠ j → IsCoprime (p i) (p j)) ∧
      f = ∏ i, (p i) ^ (e' i) := by
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

/-- **Polynomial factorization into prime powers**: every monic nonzero polynomial `f`
over a field factors as $f = \prod_{i < n} p_i^{e_i}$ where the `p_i` are distinct
monic irreducibles and the `e_i` are positive.  This combines `finset_factorization`
(which uses the UFD structure of `normalizedFactors`) with `fin_of_finset`
(pure reindexing via `Finset.equivFin`). -/
theorem exists_finpow_factorization {K : Type*} [Field K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∃ (n : ℕ) (p : Fin n → Polynomial K) (e : Fin n → ℕ),
      (∀ i, Irreducible (p i)) ∧ (∀ i, (p i).Monic) ∧ (∀ i, 0 < e i) ∧
      Function.Injective p ∧
      (∀ i j, i ≠ j → IsCoprime (p i) (p j)) ∧
      f = ∏ i, (p i) ^ (e i) := by
  obtain ⟨s, e, h1, h2, h3, h4, h5⟩ := finset_factorization f hf hf0
  exact fin_of_finset f s e h1 h2 h3 h4 h5

end Library.LinearAlgebra.PrimaryDecomposition.PolynomialFactorization
