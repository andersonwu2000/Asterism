-- Decompose lift-endpoint additivity into (A) `lift_trans_endpoint`,
-- which evaluates Mathlib's `liftPath_trans` at 1 to recast the lift of
-- γ.trans γ' as the lift of γ' starting at Γ_γ(1); and (B)
-- `lift_translation_eq_add`, the translation invariance of lifts under
-- `Circle.exp` — lift of γ' from r equals r + lift of γ' from 0.
-- Combine: LHS = liftPath γ' Γ1 _ 1 = Γ1 + liftPath γ' 0 _ 1 = RHS.
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10699

namespace Problems.pi1_circle

def lift_endpoint_trans_eq_add := @Problems.pi1_circle.s10699

end Problems.pi1_circle
