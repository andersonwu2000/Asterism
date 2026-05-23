-- Reduce QR existence to "orthogonal Q with Qᵀ*A upper-triangular":
-- pick R := Qᵀ*A; the equation A = Q*R follows from Q*Qᵀ = 1.
import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs._strategy_s10881

namespace Problems.LinearAlgebra.qr_decomposition

def main := @Problems.LinearAlgebra.qr_decomposition.s10881

end Problems.LinearAlgebra.qr_decomposition
