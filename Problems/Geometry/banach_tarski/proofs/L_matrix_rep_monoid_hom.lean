-- Build `mat` as the standard-basis matrix functor on the underlying linear maps:
--   mat T := LinearMap.toMatrix b b T.toLinearEquiv.toLinearMap,   b = (EuclideanSpace.basisFun …).toBasis.
-- The MonoidHom laws come from the End↔Matrix linear functor: `T ↦ T.toLinearEquiv.toLinearMap`
-- carries 1↦1 and (T₁*T₂)↦(·)*(·) (both `ext x; rfl`), then `LinearMap.toMatrix_one`/`toMatrix_mul`.
-- Injectivity: `LinearMap.toMatrix b b` is a LinearEquiv (injective) precomposed with the injective
--   coercions `LinearEquiv.toLinearMap_injective`/`LinearIsometryEquiv.toLinearEquiv_injective`.
-- det compatibility: `LinearMap.det_toMatrix`. Computation rule: `(LinearMap.toMatrix b b).symm`
--   is defeq `Matrix.toEuclideanLin`, so `LinearEquiv.eq_symm_apply … |>.mp rfl` reads off the matrix.
-- Sorry-free; ships as a leaf.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11491

namespace Problems.Geometry.banach_tarski

def matrix_rep_monoid_hom := @Problems.Geometry.banach_tarski.s11491

end Problems.Geometry.banach_tarski
