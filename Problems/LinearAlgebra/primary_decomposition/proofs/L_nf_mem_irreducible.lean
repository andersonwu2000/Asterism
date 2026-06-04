import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- entry_kind: Builder
-- nf_mem_irreducible: every element of (normalizedFactors f).toFinset is irreducible,
-- by Multiset.mem_toFinset + UniqueFactorizationMonoid.irreducible_of_normalized_factor.
theorem nf_mem_irreducible {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, Irreducible p := by
  intro p hp
  rw [Multiset.mem_toFinset] at hp
  exact UniqueFactorizationMonoid.irreducible_of_normalized_factor p hp

end Problems.LinearAlgebra.primary_decomposition
