-- Decompose into (1) a one-step extension lemma — any T-invariant subspace
-- of strictly smaller dimension can be enlarged to a T-invariant subspace
-- one dimension bigger (this is where alg-closedness enters, via an
-- eigenvalue of the induced endomorphism on V/U) — and (2) a pure-
-- linear-algebra packaging step that iterates such an extension starting
-- from ⊥ to build the full flag W : ℕ → Submodule K V with the four
-- properties. Sub-goal (1) carries the eigenvalue extraction;
-- sub-goal (2) handles the recursive flag assembly and rank arithmetic
-- with no alg-closed hypothesis.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10837

namespace Problems.LinearAlgebra.schur_triangularization

def invariant_flag_exists := @Problems.LinearAlgebra.schur_triangularization.s10837

end Problems.LinearAlgebra.schur_triangularization
