import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- entry_kind: Builder
-- nf_mem_count_pos: every element of normalizedFactors.toFinset has positive count
theorem nf_mem_count_pos {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      0 < (UniqueFactorizationMonoid.normalizedFactors f).count p := by
  intro p hp
  exact Multiset.count_pos.mpr (Multiset.mem_toFinset.mp hp)

end Problems.LinearAlgebra.primary_decomposition
