-- Direct leaf: x is a finite combination of the first k+1 eigenvectors b(castLE j),
-- and b i (with i > k) is orthogonal to each of them, so ⟨b i, x⟩ vanishes termwise.
-- Expand x via mem_span_range_iff_exists_fun, push inner through the sum/scalar,
-- and kill each ⟨b i, b (castLE j)⟩ by orthonormality since i ≠ castLE j (val j ≤ k < i).
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11663

namespace Problems.LinearAlgebra.eckart_young

def inner_zero_high := @Problems.LinearAlgebra.eckart_young.s11663

end Problems.LinearAlgebra.eckart_young
