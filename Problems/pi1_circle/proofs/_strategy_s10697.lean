import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_paths_homotopic_from_lift_endpoint_eq

namespace Problems.pi1_circle

-- Reduce quotient equality to path-homotopy: ⟦γa⟧ = ⟦γb⟧ in the homotopy
-- quotient holds iff `γa.Homotopic γb`. The sub-goal carries the universal
-- cover argument (ℝ simply-connected + push-down via Circle.exp), and
-- `Quotient.sound` lifts the path-level homotopy to the quotient level.
theorem s10697
    (γa γb : Path (1 : Circle) 1)
    (h : Circle.isCoveringMap_exp.liftPath γa.toContinuousMap 0
            (by simp : γa.toContinuousMap 0 = Circle.exp 0) 1
       = Circle.isCoveringMap_exp.liftPath γb.toContinuousMap 0
            (by simp : γb.toContinuousMap 0 = Circle.exp 0) 1) :
    (⟦γa⟧ : Path.Homotopic.Quotient (1 : Circle) 1) = ⟦γb⟧  := by
  have h_homotopic := paths_homotopic_from_lift_endpoint_eq γa γb h
  exact Quotient.sound h_homotopic

end Problems.pi1_circle
