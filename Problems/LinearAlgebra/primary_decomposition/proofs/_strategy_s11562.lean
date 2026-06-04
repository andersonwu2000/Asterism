import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- Direct: rewrite `f` as the product of its normalized factors, grouped by count.
-- `Monic.normalize_eq_self` turns `f` into `normalize f`, `prod_normalizedFactors_eq`
-- turns that into the multiset product, and `Finset.prod_multiset_count` regroups the
-- multiset product as `∏ p ∈ toFinset, p ^ count p`. No sub-goals needed.
theorem s11562 {K : Type*} [Field K] [DecidableEq K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    f = ∏ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      p ^ (UniqueFactorizationMonoid.normalizedFactors f).count p  := by
  conv_lhs => rw [← hf.normalize_eq_self,
    ← UniqueFactorizationMonoid.prod_normalizedFactors_eq hf0]
  exact Finset.prod_multiset_count _

end Problems.LinearAlgebra.primary_decomposition
