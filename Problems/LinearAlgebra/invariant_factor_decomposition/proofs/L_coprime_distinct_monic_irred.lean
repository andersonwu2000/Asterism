import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- entry_kind: Builder
-- coprime_distinct_monic_irred: distinct monic irreducibles over a field are coprime
-- Uses Irreducible.coprime_iff_not_dvd (PID) + associated_of_dvd + eq_of_monic_of_associated.
theorem coprime_distinct_monic_irred {K : Type*} [Field K] (a b : Polynomial K)
    (ha : a.Monic) (hb : b.Monic) (hai : Irreducible a) (hbi : Irreducible b)
    (hne : a ≠ b) : IsCoprime a b := by
  rw [hai.coprime_iff_not_dvd]
  intro hab
  exact hne (Polynomial.eq_of_monic_of_associated ha hb (hai.associated_of_dvd hbi hab))

end Problems.LinearAlgebra.invariant_factor_decomposition
