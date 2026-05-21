import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_real_paths_homotopic_rel_of_endpoints_eq

namespace Problems.pi1_circle

-- Reduce HomotopicRel-of-lifts to the general fact that any two continuous maps
-- I → ℝ with matching endpoints are HomotopicRel {0,1} (ℝ is contractible).
-- Sub-goal `real_paths_homotopic_rel_of_endpoints_eq` packages this; we feed it
-- the two liftPaths after rewriting the source endpoints via `liftPath_zero`.
theorem s10701
    (γa γb : Path (1 : Circle) 1)
    (h : Circle.isCoveringMap_exp.liftPath γa.toContinuousMap 0
            (by simp : γa.toContinuousMap 0 = Circle.exp 0) 1
       = Circle.isCoveringMap_exp.liftPath γb.toContinuousMap 0
            (by simp : γb.toContinuousMap 0 = Circle.exp 0) 1) :
    (Circle.isCoveringMap_exp.liftPath γa.toContinuousMap 0
            (by simp : γa.toContinuousMap 0 = Circle.exp 0)).HomotopicRel
    (Circle.isCoveringMap_exp.liftPath γb.toContinuousMap 0
            (by simp : γb.toContinuousMap 0 = Circle.exp 0)) {0, 1}  := by
  apply real_paths_homotopic_rel_of_endpoints_eq
  · rw [Circle.isCoveringMap_exp.liftPath_zero, Circle.isCoveringMap_exp.liftPath_zero]
  · exact h

end Problems.pi1_circle
