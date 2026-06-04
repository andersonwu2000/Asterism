import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

theorem main : ∀ {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
  [FiniteDimensional ℝ E] {K : Set E}
  (hne : K.Nonempty) (hcomp : IsCompact K) (hconv : Convex ℝ K)
  {f : E → E} (hcont : ContinuousOn f K) (hmaps : Set.MapsTo f K K),
  ∃ x ∈ K, f x = x := by sorry

end Problems.Topology.brouwer_fixed_point
