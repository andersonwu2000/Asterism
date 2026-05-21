import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_lifts_homotopic_rel_of_endpoint_eq

namespace Problems.pi1_circle

-- Reduce path-homotopy γa ~ γb to ContinuousMap.HomotopicRel of the ℝ-lifts.
-- Sub-goal: lifts in ℝ with matching endpoints are HomotopicRel {0,1} (simply-connectedness).
-- Combinator: push the lift-level homotopy down via Circle.exp using
-- `ContinuousMap.HomotopicRel.comp_continuousMap` and `liftPath_lifts`.
theorem s10700
    (γa γb : Path (1 : Circle) 1)
    (h : Circle.isCoveringMap_exp.liftPath γa.toContinuousMap 0
            (by simp : γa.toContinuousMap 0 = Circle.exp 0) 1
       = Circle.isCoveringMap_exp.liftPath γb.toContinuousMap 0
            (by simp : γb.toContinuousMap 0 = Circle.exp 0) 1) :
    γa.Homotopic γb  := by
  have h_hr := lifts_homotopic_rel_of_endpoint_eq γa γb h


  have h_exp_a : (⟨Circle.exp, Circle.exp.continuous⟩ : C(ℝ, Circle)).comp
                    (Circle.isCoveringMap_exp.liftPath γa.toContinuousMap 0
                       (by simp : γa.toContinuousMap 0 = Circle.exp 0))
                  = γa.toContinuousMap := by
    apply DFunLike.ext
    intro t
    exact congrFun (Circle.isCoveringMap_exp.liftPath_lifts γa.toContinuousMap 0 _) t
  have h_exp_b : (⟨Circle.exp, Circle.exp.continuous⟩ : C(ℝ, Circle)).comp
                    (Circle.isCoveringMap_exp.liftPath γb.toContinuousMap 0
                       (by simp : γb.toContinuousMap 0 = Circle.exp 0))
                  = γb.toContinuousMap := by
    apply DFunLike.ext
    intro t
    exact congrFun (Circle.isCoveringMap_exp.liftPath_lifts γb.toContinuousMap 0 _) t
  have h_circle := h_hr.comp_continuousMap (⟨Circle.exp, Circle.exp.continuous⟩ : C(ℝ, Circle))
  rw [h_exp_a, h_exp_b] at h_circle
  exact h_circle



end Problems.pi1_circle
