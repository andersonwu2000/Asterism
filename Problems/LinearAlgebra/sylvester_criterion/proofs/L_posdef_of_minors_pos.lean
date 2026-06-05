-- Sylvester reverse direction: induction on the dimension n (revert M first so the
-- inductive hypothesis quantifies over every n×n matrix).
--  • base `posdef_empty`: the 0×0 matrix is PosDef vacuously.
--  • step `posdef_succ_step`: given ih (the criterion for n) plus the (n+1) leading
--    minors, the Schur-complement argument upgrades to PosDef.
-- `induction` is the combinator; each branch is strictly simpler (base trivial; step
-- has ih in hand, so it no longer carries the induction setup).
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11603

namespace Problems.LinearAlgebra.sylvester_criterion

def posdef_of_minors_pos := @Problems.LinearAlgebra.sylvester_criterion.s11603

end Problems.LinearAlgebra.sylvester_criterion
