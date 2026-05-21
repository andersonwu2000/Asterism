import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- q_uniform_smallness_on_unit_segment: uniform bound ‖Q(z+t·h)-Q(z)‖≤ε for t∈[0,1]
-- from ContinuousAt Q z: extract a metric ball of radius δ around z; for h in ball 0 δ,
-- ‖t·h‖ ≤ ‖h‖ < δ forces z+t·h ∈ ball z δ for all t∈[0,1].
theorem q_uniform_smallness_on_unit_segment
    (Q : ℂ → ℂ) (z : ℂ) (h_cont : ContinuousAt Q z) :
    ∀ ε : ℝ, 0 < ε → ∀ᶠ h : ℂ in nhds 0,
      ∀ t : ℝ, t ∈ Set.Icc (0:ℝ) 1 → ‖Q (z + (t : ℂ) * h) - Q z‖ ≤ ε := by
  intro ε hε
  rw [Metric.continuousAt_iff] at h_cont
  obtain ⟨δ, hδ, hball⟩ := h_cont ε hε
  apply Filter.eventually_of_mem (Metric.ball_mem_nhds 0 hδ)
  intro h hh t ht
  rw [Metric.mem_ball, dist_zero_right] at hh
  have hle : dist (Q (z + ↑t * h)) (Q z) < ε := by
    apply hball
    rw [dist_eq_norm]
    simp only [add_sub_cancel_left]
    calc ‖(t : ℂ) * h‖ = ‖(t : ℂ)‖ * ‖h‖ := norm_mul _ _
      _ ≤ 1 * ‖h‖ := by
          apply mul_le_mul_of_nonneg_right _ (norm_nonneg _)
          rw [Complex.norm_real, Real.norm_of_nonneg ht.1]
          exact ht.2
      _ = ‖h‖ := one_mul _
      _ < δ := hh
  rw [dist_comm, dist_eq_norm] at hle
  rw [norm_sub_rev]
  linarith

end residue_thm

end Problems
