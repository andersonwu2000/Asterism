import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

theorem main : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
  {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
  ∀ {P : X → X}, IsMetricProjector K P →
  ∀ x y, ‖P x - P y‖ ≤ ‖x - y‖ := by sorry

end Problems.proj_nonexpansive
