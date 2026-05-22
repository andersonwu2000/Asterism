-- Direct construction by `Nat.rec` on a sigma-packaged `{U // T-invariant U}`:
-- the base picks `⊥` (vacuously invariant), and each successor uses `Classical.choose`
-- on the saturated extension hypothesis to produce the next invariant subspace; the four
-- conjuncts then unpack from the recursion definition and the choice spec.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10847

namespace Problems.LinearAlgebra.schur_triangularization

def extension_iteration_sequence := @Problems.LinearAlgebra.schur_triangularization.s10847

end Problems.LinearAlgebra.schur_triangularization
