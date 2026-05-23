-- Reduce orthogonal-upper-triangularizer existence to two independent pieces:
--   (a) `A.det ≠ 0` lifts to linear independence of A's columns (`A.transpose`);
--   (b) any A with linearly-independent columns admits the orthogonal Q with
--       upper-triangular `Qᵀ * A` (the Gram-Schmidt-driven core).
-- Combinator just threads (a) into (b).
import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs._strategy_s10882

namespace Problems.LinearAlgebra.qr_decomposition

def orthogonal_upper_triangularizer := @Problems.LinearAlgebra.qr_decomposition.s10882

end Problems.LinearAlgebra.qr_decomposition
