import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

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
end Problems.LinearAlgebra.primary_decomposition
