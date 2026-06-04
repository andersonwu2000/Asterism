import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- ray_retraction_from_parameter: witness r x := x + t x • (x - f x); continuity from hcont+htcont,
-- MapsTo from htnorm (norm=1 iff on sphere), identity-on-sphere from htsphere (t=0 there).
theorem ray_retraction_from_parameter
    {n : ℕ}
    {f : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hcont : ContinuousOn f (Metric.closedBall 0 1))
    (t : EuclideanSpace ℝ (Fin n) → ℝ)
    (htcont : ContinuousOn t (Metric.closedBall 0 1))
    (htnorm : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1,
        ‖x + t x • (x - f x)‖ = 1)
    (htsphere : ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, t x = 0) :
    ∃ r : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn r (Metric.closedBall 0 1) ∧
      Set.MapsTo r
          (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
          (Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, r x = x := by
  refine ⟨fun x => x + t x • (x - f x), ?_, ?_, ?_⟩
  · apply ContinuousOn.add continuousOn_id
    apply ContinuousOn.smul htcont
    exact continuousOn_id.sub hcont
  · intro x hx
    rw [Metric.mem_sphere, dist_zero_right]
    exact htnorm x hx
  · intro x hx
    simp [htsphere x hx]

end Problems.Topology.brouwer_fixed_point
