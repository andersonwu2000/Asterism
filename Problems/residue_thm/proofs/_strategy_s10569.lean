import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_eps_bump_radius_avoiding_path
import Problems.residue_thm.proofs.L_winding_const_on_open_ball_off_image

namespace Problems.residue_thm

-- For w on the ε-sphere around a:
-- (1) `eps_bump_radius_avoiding_path` (Builder, compactness): there exists r > ε
--     such that γ still avoids the closed r-ball around a, so w sits strictly
--     inside the open r-ball.
-- (2) `winding_const_on_open_ball_off_image` (Backward, locally-constant winding):
--     when γ avoids the closed r-ball around z, windingNumber γ is constant on
--     the open r-ball, equal to windingNumber γ z. Apply with z = a.
theorem s10569
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (hε_pos : 0 < ε)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    ∀ w ∈ Metric.sphere a ε,
      Complex.windingNumber γ w = Complex.windingNumber γ a  := by
  intro w hw
  obtain ⟨r, hr_gt, h_avoid_r⟩ :=
    eps_bump_radius_avoiding_path hγ hε_pos hε_sep
  have hr_pos : 0 < r := lt_trans hε_pos hr_gt
  have hw_dist : dist w a = ε := Metric.mem_sphere.mp hw
  have hw_in_ball : w ∈ Metric.ball a r := by
    rw [Metric.mem_ball]; exact hw_dist ▸ hr_gt
  exact winding_const_on_open_ball_off_image hγ hclosed hr_pos h_avoid_r w hw_in_ball


end Problems.residue_thm
