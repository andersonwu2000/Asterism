import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- entry_kind: Builder
-- nf_mem_monic: members of normalizedFactors f toFinset are monic, via
-- Polynomial.mem_normalizedFactors_iff which gives Irreducible ∧ Monic ∧ dvd.
theorem nf_mem_monic {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p.Monic := by
  intro p hp
  rw [Multiset.mem_toFinset] at hp
  exact ((Polynomial.mem_normalizedFactors_iff hf0).mp hp).2.1

end Problems.LinearAlgebra.primary_decomposition
