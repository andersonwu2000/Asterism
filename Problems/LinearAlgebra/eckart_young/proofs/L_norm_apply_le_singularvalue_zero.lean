-- Reduce the pointwise bound ‖A x‖ ≤ σ₀‖x‖ to its squared form ‖A x‖² ≤ σ₀²‖x‖²
-- (the genuine spectral content: σ₀² is the top eigenvalue of A†A), then take square
-- roots — both sides are nonnegative (σ₀ ≥ 0, ‖x‖ ≥ 0), so le_of_sq_le_sq closes it.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11639

namespace Problems.LinearAlgebra.eckart_young

def norm_apply_le_singularvalue_zero := @Problems.LinearAlgebra.eckart_young.s11639

end Problems.LinearAlgebra.eckart_young
