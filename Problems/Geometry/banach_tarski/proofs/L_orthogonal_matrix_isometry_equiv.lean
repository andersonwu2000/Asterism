-- Decompose: orthogonal A → IsometryEquiv via a LinearIsometryEquiv, then `.toIsometryEquiv`.
-- One sub-goal: `orthogonal_matrix_preserves_inner` — `toEuclideanLin A` preserves the real inner
-- product (the orthogonality content: ⟪Ax,Ay⟫ = ⟪x,AᵀAy⟫ = ⟪x,y⟫). The rest is pure structural
-- packaging on top: `LinearMap.isometryOfInner` turns the inner-preservation into a `LinearIsometry`
-- f; f is injective hence (finite dim) surjective via `LinearMap.injective_iff_surjective`;
-- `LinearIsometryEquiv.ofSurjective` upgrades f to a `≃ₗᵢ`; `.toIsometryEquiv` is the witness, and
-- its action is defeq to `toEuclideanLin A` (rfl). The sub-goal is strictly simpler: a pure
-- inner-product/matrix identity, no existential or isometry packaging.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11390

namespace Problems.Geometry.banach_tarski

def orthogonal_matrix_isometry_equiv := @Problems.Geometry.banach_tarski.s11390

end Problems.Geometry.banach_tarski
