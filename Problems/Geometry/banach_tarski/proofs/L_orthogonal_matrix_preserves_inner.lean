-- Direct proof: `Aᵀ A = 1 ⟹ ⟪Ax, Ay⟫ = ⟪x, y⟫`. Expand both Euclidean inners
-- componentwise (`PiLp.inner_apply`), reduce `toEuclideanLin A` to `A.mulVec`, and
-- rewrite the real scalar inner `⟪a,b⟫_ℝ = a*b` (`hr`). The remaining sum is the
-- dot-product identity `(A*ᵥx) ⬝ᵥ (A*ᵥy) = x ⬝ᵥ y` (`key`), closed by
-- `dotProduct_mulVec`/`mulVec_transpose`/`mulVec_mulVec` + `hA` + `one_mulVec`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11391

namespace Problems.Geometry.banach_tarski

def orthogonal_matrix_preserves_inner := @Problems.Geometry.banach_tarski.s11391

end Problems.Geometry.banach_tarski
