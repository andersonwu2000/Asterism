import Mathlib
import Problems.pi1_circle.Defs

namespace Problems.pi1_circle

-- lift_trans_endpoint: liftPath_trans + Path.target collapses the lifted concatenation to
-- the endpoint of the second half's lift starting at the first half's endpoint.
theorem lift_trans_endpoint
    (γ γ' : Path (1 : Circle) 1)
    (h_γ' : γ'.toContinuousMap 0 = Circle.exp
      (Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
        (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1)) :
    Circle.isCoveringMap_exp.liftPath (γ.trans γ').toContinuousMap 0
        (by simp : (γ.trans γ').toContinuousMap 0 = Circle.exp 0) 1
      = Circle.isCoveringMap_exp.liftPath γ'.toContinuousMap
          (Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1) h_γ' 1 := by
  exact (DFunLike.congr_fun
    (Circle.isCoveringMap_exp.liftPath_trans (by simp : (1:Circle) = Circle.exp 0) γ γ') 1).trans
    (Path.target _)

end Problems.pi1_circle
