-- On `Kᗮ` (K = span of the top-k right singular vectors of `T`), `T` shrinks by `σ_k`.
-- Reduce to the squared bound `‖T y‖² ≤ σ_k² ‖y‖²` (the inner-product / eigenvalue content,
-- delegated to `bottom_span_norm_sq_le`), then lift through `le_of_sq_le_sq` since both
-- `σ_k * ‖y‖` and the norms are nonnegative.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11659

namespace Problems.LinearAlgebra.eckart_young

def bottom_span_norm_le := @Problems.LinearAlgebra.eckart_young.s11659

end Problems.LinearAlgebra.eckart_young
