-- Upgrade mathlib's prime-power torsion decomposition to *monic* irreducible generators.
-- `Module.equiv_directSum_of_isTorsion` gives the decomposition with irreducible (not nec.
-- monic) generators `p i`; for each, `exists_monic_quot_equiv` produces a monic irreducible
-- associate `q i` together with a quotient linear-equiv (spans of `a^e` and `q^e` agree).
-- `choose` extracts the family `q`, and `DirectSum.congrLinearEquiv` transports the direct
-- sum component-wise.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11566

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def monic_directsum_of_torsion := @Problems.LinearAlgebra.invariant_factor_decomposition.s11566

end Problems.LinearAlgebra.invariant_factor_decomposition
