import Mathlib

namespace Library.LinearAlgebra.PrimaryDecomposition.NormalizedFactors

-- entry_kind: Builder
-- nf_mem_count_pos: every element of normalizedFactors.toFinset has positive count
theorem nf_mem_count_pos {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      0 < (UniqueFactorizationMonoid.normalizedFactors f).count p := by
  intro p hp
  exact Multiset.count_pos.mpr (Multiset.mem_toFinset.mp hp)

-- entry_kind: Builder
-- nf_mem_irreducible: every element of (normalizedFactors f).toFinset is irreducible,
-- by Multiset.mem_toFinset + UniqueFactorizationMonoid.irreducible_of_normalized_factor.
theorem nf_mem_irreducible {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, Irreducible p := by
  intro p hp
  rw [Multiset.mem_toFinset] at hp
  exact UniqueFactorizationMonoid.irreducible_of_normalized_factor p hp

-- entry_kind: Builder
-- nf_mem_monic: members of normalizedFactors f toFinset are monic, via
-- Polynomial.mem_normalizedFactors_iff which gives Irreducible ∧ Monic ∧ dvd.
theorem nf_mem_monic {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p.Monic := by
  intro p hp
  rw [Multiset.mem_toFinset] at hp
  exact ((Polynomial.mem_normalizedFactors_iff hf0).mp hp).2.1

-- entry_kind: Builder
-- nf_mem_pairwise_coprime: distinct normalized factors of f are pairwise coprime —
-- reduces to showing p ∤ q via Irreducible.coprime_iff_not_dvd, then uses
-- normalizedFactors_eq_of_dvd to derive p = q from p ∣ q, contradicting p ≠ q.
theorem nf_mem_pairwise_coprime {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
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

-- Direct: rewrite `f` as the product of its normalized factors, grouped by count.
-- `Monic.normalize_eq_self` turns `f` into `normalize f`, `prod_normalizedFactors_eq`
-- turns that into the multiset product, and `Finset.prod_multiset_count` regroups the
-- multiset product as `∏ p ∈ toFinset, p ^ count p`. No sub-goals needed.
theorem nf_prod_pow_count {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    f = ∏ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      p ^ (UniqueFactorizationMonoid.normalizedFactors f).count p  := by
  conv_lhs => rw [← hf.normalize_eq_self,
    ← UniqueFactorizationMonoid.prod_normalizedFactors_eq hf0]
  exact Finset.prod_multiset_count _

end Library.LinearAlgebra.PrimaryDecomposition.NormalizedFactors
