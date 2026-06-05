-- Direct leaf: `b i` (high eigenvector, `i > k`) is orthogonal to the top-(k+1) span.
-- Show `b i ∈ (span {b (castLE j)})ᗮ` by span-induction: on generators it is the
-- orthonormality of the eigenbasis (`b.orthonormal.2`, indices distinct since `castLE j ≤ k < i`),
-- closed under `+`/`•` via `inner_add_right`/`inner_smul_right`; then `inner_left_of_mem_orthogonal hx`.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11661

namespace Problems.LinearAlgebra.eckart_young

def inner_eigenvector_high_eq_zero := @Problems.LinearAlgebra.eckart_young.s11661

end Problems.LinearAlgebra.eckart_young
