-- Reduce to the abstract monic structure theorem for finite torsion K[X]-modules.
-- `Module.AEval' T` is a finitely-generated torsion K[X]-module: torsion comes from
-- `Module.AEval.isTorsion_of_finiteDimensional`, finiteness is the standard AEval instance.
-- The whole remaining content (mathlib's `equiv_directSum_of_isTorsion` upgraded so the prime
-- generators are *monic* irreducibles) lives in the single abstract sub-goal
-- `monic_directsum_of_torsion`. Instances are supplied explicitly to dodge the `AEval'`
-- AddCommGroup/Module/Finite synthesis diamond.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11564

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def primary_form := @Problems.LinearAlgebra.invariant_factor_decomposition.s11564

end Problems.LinearAlgebra.invariant_factor_decomposition
