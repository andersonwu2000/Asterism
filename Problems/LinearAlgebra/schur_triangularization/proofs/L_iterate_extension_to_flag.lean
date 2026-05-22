-- Two-step packaging: (1) `extension_iteration_sequence` constructs the recursive
-- flag W : ℕ → Submodule K V from the saturated one-step extension hypothesis,
-- giving W 0 = ⊥, the chain, T-invariance at every level, and the *step* rank
-- equation `finrank (W (i+1)) = min (finrank (W i) + 1) (finrank V)`.
-- (2) `rank_chain_min_eq` is a pure ℕ-induction lemma converting that step rank
-- equation, together with W 0 = ⊥, into the closed-form `finrank (W i) = min i (finrank V)`.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10844

namespace Problems.LinearAlgebra.schur_triangularization

def iterate_extension_to_flag := @Problems.LinearAlgebra.schur_triangularization.s10844

end Problems.LinearAlgebra.schur_triangularization
