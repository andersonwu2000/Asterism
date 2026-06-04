import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_compact_convex_origin_interior_homeo_unit_ball
import Problems.Topology.brouwer_fixed_point.proofs.L_recenter_compact_convex_to_origin

namespace Problems.Topology.brouwer_fixed_point

-- Two-step decomposition: (a) translate by an interior point so 0 lies in the
-- interior of the translated set T (compactness and convexity are preserved);
-- (b) any compact convex T with 0 in its interior is homeomorphic to the
-- closed unit ball (radial map via the Minkowski gauge in finite dimension).
theorem s10811
    {n : ℕ} {S : Set (EuclideanSpace ℝ (Fin n))}
    (hne : S.Nonempty) (hcomp : IsCompact S) (hconv : Convex ℝ S)
    (hint : (interior S).Nonempty) :
    Nonempty (S ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)  := by
  obtain ⟨p, hp⟩ := hint
  have h_recenter := recenter_compact_convex_to_origin hcomp hconv hp
  obtain ⟨T, hTcomp, hTconv, hT0, hST⟩ := h_recenter
  obtain ⟨φST⟩ := hST
  have h_gauge := compact_convex_origin_interior_homeo_unit_ball hTcomp hTconv hT0
  obtain ⟨φTB⟩ := h_gauge
  exact ⟨φST.trans φTB⟩

end Problems.Topology.brouwer_fixed_point
