import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_exists_ray_retraction_of_no_fixed_point
import Problems.Topology.brouwer_fixed_point.proofs.L_extend_subtype_self_map_no_fp

namespace Problems.Topology.brouwer_fixed_point

-- Subtype `g` with no fixed point ⇒ ambient ball self-map `f` with no
-- fixed point on the closed ball ⇒ apply proved sibling
-- `exists_ray_retraction_of_no_fixed_point` to obtain the retraction.
-- The only substantive step is the subtype-to-ambient lift; the closer
-- is the sibling.
theorem s10833
    {n : ℕ} (_hn : 0 < n)
    (_hno_retr : ¬ ∃ r : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn r (Metric.closedBall 0 1) ∧
      Set.MapsTo r (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, r x = x)
    (g : Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 →
         Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    (_hcont : Continuous g)
    (hnofp : ∀ y, g y ≠ y) :
    ∃ r : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn r (Metric.closedBall 0 1) ∧
      Set.MapsTo r (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, r x = x  := by
  have h_ext := extend_subtype_self_map_no_fp _hn g _hcont hnofp
  obtain ⟨f, hcont, hmaps, hnofp_amb⟩ := h_ext
  exact exists_ray_retraction_of_no_fixed_point _hn hcont hmaps hnofp_amb

end Problems.Topology.brouwer_fixed_point
