-- Induction on `n`: the parent's universally-quantified statement splits
-- into a vacuous `Fin 0` base case (`lu_base`) and a one-step inductive
-- lift (`lu_step`), combined by `induction n with`.
import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs._strategy_s11322

namespace Problems.LinearAlgebra.lu_decomposition

def main := @Problems.LinearAlgebra.lu_decomposition.s11322

end Problems.LinearAlgebra.lu_decomposition
