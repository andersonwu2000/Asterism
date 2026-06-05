-- ‖A‖ = σ₀(A) by antisymmetry of two operator-norm bounds.
-- (≤) every vector satisfies ‖A x‖ ≤ σ₀‖x‖ since σ₀² is the top eigenvalue of A†A;
-- (≥) the top right-singular vector achieves ‖A x‖ = σ₀‖x‖, so σ₀ ≤ ‖A‖.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11636

namespace Problems.LinearAlgebra.eckart_young

def opnorm_eq_singularvalues_zero := @Problems.LinearAlgebra.eckart_young.s11636

end Problems.LinearAlgebra.eckart_young
