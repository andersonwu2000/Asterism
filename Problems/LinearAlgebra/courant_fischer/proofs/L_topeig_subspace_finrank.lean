-- S = span of the top (k+1) eigenvectors; finrank = #generators since they are independent.
-- hA: the eigenvectorBasis vectors over the index set {i ≤ k} are linearly independent
--     (so the span's dimension equals the number of generators);
-- hB: that index set has exactly k+1 elements.
-- Combine: rewrite the image as a range, apply finrank_span_eq_card hA, close with hB.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11629

namespace Problems.LinearAlgebra.courant_fischer

def topeig_subspace_finrank := @Problems.LinearAlgebra.courant_fischer.s11629

end Problems.LinearAlgebra.courant_fischer
