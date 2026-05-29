-- Direct proof (leaf-bypass): `Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))`
-- is a monoid hom `FreeGroup (Fin 2) →* ℝ`; show it is ≡ 1 by free-group induction
-- (generators have det 1 via hdetA/hdetB; closed under one/mul/inv), then transport
-- the value back to `LinearMap.det` of the lift via hmatdet.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11485

namespace Problems.Geometry.banach_tarski

def lift_det_one := @Problems.Geometry.banach_tarski.s11485

end Problems.Geometry.banach_tarski
