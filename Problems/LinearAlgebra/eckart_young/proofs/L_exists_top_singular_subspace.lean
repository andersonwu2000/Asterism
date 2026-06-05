-- Eckart–Young lower bound, spectral half: build the top-(k+1) right-singular subspace.
-- `V` is the span of the first k+1 eigenvectors of `T† ∘ₗ T` (sorted by decreasing
-- eigenvalue σ_i²), supplied by `hT.eigenvectorBasis`. The goal's two conjuncts split into
-- two independent, strictly-smaller obligations on this fixed `V`:
--   `finrank_span_top_singular_eigenvectors` — `V` has dimension exactly k+1 (k+1 vectors
--     drawn from an orthonormal basis are linearly independent);
--   `norm_lower_bound_top_singular_span` — on `V`, `σ_k‖x‖ ≤ ‖T x‖` (the spectral content:
--     every eigenvalue contributing to `x` is ≥ σ_k²).
-- Combinator: `refine ⟨V, ?_, ?_⟩` then discharge each conjunct by its sub-goal.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11650

namespace Problems.LinearAlgebra.eckart_young

def exists_top_singular_subspace := @Problems.LinearAlgebra.eckart_young.s11650

end Problems.LinearAlgebra.eckart_young
