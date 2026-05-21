import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_integral_eq_diff_on_ball

namespace Problems.residue_thm

-- Cauchy on a ball via primitive existence on a disk + FTC along a closed C¹ path.
-- (1) `DifferentiableOn.isExactOn_ball` (Mathlib) gives a primitive `F` of `f` on the ball;
-- (2) sub-goal `path_integral_eq_diff_on_ball` rewrites the path integral as `F(γ 1) − F(γ 0)`
--     (specialization of the proved `path_integral_eq_primitive_diff` with `U := ball z₀ R`);
-- (3) `hclosed` collapses the difference to `0`.
theorem s10400
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ}
    (hf : DifferentiableOn ℂ f (Metric.ball z₀ R))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) (Metric.ball z₀ R))
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0  := by
  obtain ⟨F, hF⟩ := hf.isExactOn_ball
  have h_ftc := path_integral_eq_diff_on_ball hF hγ hγU
  rw [h_ftc, hclosed, sub_self]

end Problems.residue_thm
