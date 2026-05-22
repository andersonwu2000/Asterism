-- Decompose into (1) a packaged step lemma — under the parent's step-existence and
-- finrank hypotheses, for each n < finrank K V there is `vnext ∈ W (n+1)` with
-- `W n ⊔ span K {vnext} = W (n+1)` (folds the dimension argument into the step) —
-- and (2) a pure iterative construction — given that packaged step, build the
-- `Fin (finrank K V) → V` sequence and prove the span equality by induction on j.
-- (1) is a one-shot rank/sup argument; (2) carries the dependent recursion.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10845

namespace Problems.LinearAlgebra.schur_triangularization

def flag_seq_build_from_step := @Problems.LinearAlgebra.schur_triangularization.s10845

end Problems.LinearAlgebra.schur_triangularization
