-- Reduce to Gram-Schmidt on LI vectors in EuclideanSpace:
--   (1) transport LI of A.transpose through (EuclideanSpace.equiv).symm,
--   (2) Gram-Schmidt existence (orthonormal q with triangular span) for any
--       LI family in EuclideanSpace ℝ (Fin n) — the actual content.
-- Combinator: forward both sub-goals; the witness from (2) is exactly the
-- existential the parent asks for, with v := (Eucl.equiv).symm ∘ A.transpose.
import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs._strategy_s10885

namespace Problems.LinearAlgebra.qr_decomposition

def gram_schmidt_ortho_triangular_span := @Problems.LinearAlgebra.qr_decomposition.s10885

end Problems.LinearAlgebra.qr_decomposition
