import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_exists_self_homeo_sending_to_unit_ball

namespace Problems.Topology.brouwer_fixed_point

-- Reduce subtype homeomorphism to existence of a self-homeomorphism of the
-- ambient Euclidean space sending T onto the closed unit ball. The standard
-- realization is the Minkowski gauge rescale, but this strategy abstracts
-- that geometric content into a single sub-goal; the parent only does
-- subtype/image plumbing via `Homeomorph.image` + `Homeomorph.setCongr`.
theorem s10812
    {n : ℕ} {T : Set (EuclideanSpace ℝ (Fin n))}
    (hcomp : IsCompact T) (hconv : Convex ℝ T)
    (h0 : (0 : EuclideanSpace ℝ (Fin n)) ∈ interior T) :
    Nonempty (T ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)  := by
  have h_sub := exists_self_homeo_sending_to_unit_ball hcomp hconv h0
  obtain ⟨e, he⟩ := h_sub
  exact ⟨(e.image T).trans (Homeomorph.setCongr he)⟩

end Problems.Topology.brouwer_fixed_point
