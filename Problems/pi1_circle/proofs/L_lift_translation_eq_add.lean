-- Decompose by uniqueness of lifts (`IsCoveringMap.eq_liftPath_iff'`):
-- the candidate ContinuousMap `g(t) = Γ0(t) + r` (Γ0 = lift of γ' from 0)
-- projects to γ' via `Circle.exp_add` + `Circle.exp r = 1` and satisfies
-- `g 0 = r`, hence equals `liftPath γ' r hr` as continuous maps. Specialize
-- at t = 1 to read off `liftPath γ' r hr 1 = Γ0 1 + r = r + Γ0 1`. The single
-- sub-goal `lift_translation_proj_eq_loop` packages the projection identity
-- pointwise (uses `Circle.exp_add`, `liftPath_lifts`, and `γ'(0) = 1`).
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10702

namespace Problems.pi1_circle

def lift_translation_eq_add := @Problems.pi1_circle.s10702

end Problems.pi1_circle
