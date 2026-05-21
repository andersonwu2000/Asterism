import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_partition_subdivides_path_in_ball
import Problems.residue_thm.proofs.L_uniform_ball_thickening_of_path

namespace Problems.residue_thm

-- Decompose: (A) compact γ([0,1]) ⊆ open U has a uniform δ-thickening still in U,
-- (B) C¹ (hence uniformly continuous) γ admits a partition into pieces of γ-image
-- diameter < δ; combining gives centers c_i := γ(t_i), radii r_i := δ, and the
-- per-segment MapsTo into balls.
theorem s10493
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    ∃ (n : ℕ) (t : ℕ → ℝ) (centers : ℕ → ℂ) (radii : ℕ → ℝ),
      t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i+1)) ∧
      (∀ i, i < n → 0 < radii i) ∧
      (∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U) ∧
      (∀ i, i < n →
        Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i)))  := by
  obtain ⟨δ, hδpos, hδball⟩ := uniform_ball_thickening_of_path hU hγ hmaps
  obtain ⟨n, t, ht0, htn, hmono, hin, hcov⟩ :=
    partition_subdivides_path_in_ball hU hγ hmaps δ hδpos
  refine ⟨n, t, fun i => γ (t i), fun _ => δ, ht0, htn, hmono,
    fun i _ => hδpos,
    fun i hi => hδball (t i) (hin i hi.le),
    hcov⟩

end Problems.residue_thm
