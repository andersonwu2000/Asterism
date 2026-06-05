-- Construct W as the span of the bottom eigenvectors {bᵢ : k ≤ i}, abstracting
-- the eigenvector basis to a generic orthonormal basis `b`.
-- finrank_span_image_high: |{i : k ≤ i}| = n−k gives the dimension count.
-- inner_eq_zero_of_mem_span_high: orthonormality kills ⟪bᵢ, x⟫ for i<k (x ∈ bottom modes).
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11625

namespace Problems.LinearAlgebra.courant_fischer

def bottom_eigenspace_with_support := @Problems.LinearAlgebra.courant_fischer.s11625

end Problems.LinearAlgebra.courant_fischer
