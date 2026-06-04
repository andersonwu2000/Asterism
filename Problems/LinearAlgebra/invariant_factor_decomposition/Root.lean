-- Invariant factor decomposition = primary (prime-power) decomposition, then
-- recombination of the prime-power cyclic summands into a divisibility chain.
-- `primary_form` (SG1): the K[X]-module `AEval' T` splits as `⨁ K[X]/(p i ^ e i)`
--   with `p i` monic irreducible (mathlib structure theorem for f.g. torsion PID modules).
-- `recombine_invariant_factors` (SG2, abstract over T): regroup any such prime-power
--   direct sum into invariant factors `f 0 ∣ f 1 ∣ ... ` (monic, non-unit) via CRT.
-- Combinator: transport `AEval' T` across `equiv1.trans equiv2`; side conditions from SG2.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11563

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def main := @Problems.LinearAlgebra.invariant_factor_decomposition.s11563

end Problems.LinearAlgebra.invariant_factor_decomposition
