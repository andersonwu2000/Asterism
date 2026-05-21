import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_lift_translation_eq_add
import Problems.pi1_circle.proofs.L_lift_trans_endpoint

namespace Problems.pi1_circle

-- Decompose lift-endpoint additivity into (A) `lift_trans_endpoint`,
-- which evaluates Mathlib's `liftPath_trans` at 1 to recast the lift of
-- γ.trans γ' as the lift of γ' starting at Γ_γ(1); and (B)
-- `lift_translation_eq_add`, the translation invariance of lifts under
-- `Circle.exp` — lift of γ' from r equals r + lift of γ' from 0.
-- Combine: LHS = liftPath γ' Γ1 _ 1 = Γ1 + liftPath γ' 0 _ 1 = RHS.
theorem s10699
    (γ γ' : Path (1 : Circle) 1) :
    Circle.isCoveringMap_exp.liftPath (γ.trans γ').toContinuousMap 0
        (by simp : (γ.trans γ').toContinuousMap 0 = Circle.exp 0) 1
      = Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
          (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1
        + Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap 0
          (by simp : γ'.toContinuousMap 0 = Circle.exp 0) 1  := by
  set Γ1 : ℝ := Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
                (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 with hΓ1
  have h_γ' : γ'.toContinuousMap 0 = Circle.exp Γ1 := by
    have h_lifts := congr_fun
      (Circle.isCoveringMap_exp.liftPath_lifts γ.toContinuousMap 0
        (by simp : γ.toContinuousMap 0 = Circle.exp 0)) 1
    have hExpΓ1 : Circle.exp Γ1 = γ.toContinuousMap 1 := by
      simpa [hΓ1] using h_lifts
    simp [hExpΓ1]
  have h_lift_trans_endpoint := lift_trans_endpoint γ γ' h_γ'
  have h_lift_translation_eq_add := lift_translation_eq_add γ' Γ1 h_γ'
  linarith [h_lift_trans_endpoint, h_lift_translation_eq_add]


end Problems.pi1_circle
