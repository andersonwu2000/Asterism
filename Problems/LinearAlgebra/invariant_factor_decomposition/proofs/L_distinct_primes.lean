-- Deduplicate the finite family {p i.val : 0 < e i} into distinct monic irreducible primes.
-- `enum_finite_image`: enumerate the finite image of any f : α → β as an injective q : Fin s → β
--   plus a key α → Fin s and surjectivity-onto-image — pure finiteness plumbing, no field theory.
-- `coprime_distinct_monic_irred`: two distinct monic irreducibles are coprime — leaf UFD fact.
-- Closer: q from the enumeration is monic/irreducible (each value is some p a.val) and pairwise
--   coprime (distinct ⇒ q t ≠ q t' by injectivity ⇒ leaf); p i.val = q (key i) is the key eq.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11580

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def distinct_primes := @Problems.LinearAlgebra.invariant_factor_decomposition.s11580

end Problems.LinearAlgebra.invariant_factor_decomposition
