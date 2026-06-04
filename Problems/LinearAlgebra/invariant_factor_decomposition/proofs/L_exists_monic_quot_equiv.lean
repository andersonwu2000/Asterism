-- Take q := normalize a, the monic associate of the irreducible a.
-- It is irreducible (associated to a) and monic; since a^n and q^n are associated,
-- their generated spans coincide, so the quotients are equal — Submodule.quotEquivOfEq
-- supplies the K[X]-linear iso. Direct leaf proof, no sub-goals.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11567

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def exists_monic_quot_equiv := @Problems.LinearAlgebra.invariant_factor_decomposition.s11567

end Problems.LinearAlgebra.invariant_factor_decomposition
