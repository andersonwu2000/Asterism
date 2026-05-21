import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_kernel_diff_outer_inner
import Problems.residue_thm.proofs.L_kernel_integral_linear_split
import Problems.residue_thm.proofs.L_slope_integral_diff_radius_indep

namespace Problems.residue_thm

-- Algebraically `f w / (w-z) = f z * (w-z)⁻¹ + (f w - f z)/(w-z)` on each circle
-- (the circles avoid z, so the split is valid pointwise).  Linearity then splits
-- the parent difference into a Cauchy-kernel piece (f z * 2πi) and a slope piece (0):
--   * `cauchy_kernel_diff_outer_inner`: ∮_r (w-z)⁻¹ − ∮_ε (w-z)⁻¹ = 2πi
--     (outer = Cauchy on ball z₀ r with the inverse kernel; inner = single-disk
--     Cauchy on ball z₀ ε where (w-z)⁻¹ is analytic since z ∉ ball z₀ ε).
--   * `slope_integral_diff_radius_indep`: ∮_r (f w - f z)/(w-z) − ∮_ε ··· = 0
--     (`dslope f z` is analytic on `ball z₀ R \ {z₀}` — f's pole at z₀ is the only
--     one — so the existing punctured-ball radius-independence sibling closes it).
--   * `kernel_integral_linear_split`: pure linearity-of-circle-integrals identity
--     bridging the parent integrand to the split form (algebra + integrability).
-- None of the sub-goals reduces to the multiply-punctured Cauchy bridge: each
-- circle integral on the kernel is a single-disk evaluation (or single-puncture
-- radius-indep), and the slope's removable singularity at z merges the two
-- punctures into one.
theorem s10420
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), f w / (w - z))
      - (∮ w in C(z₀, ε), f w / (w - z))
      = 2 * (Real.pi : ℂ) * Complex.I * f z  := by
  have h_ker :
      (∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹)
        = 2 * (Real.pi : ℂ) * Complex.I :=
    cauchy_kernel_diff_outer_inner hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  have h_slp :
      (∮ w in C(z₀, r), (f w - f z) / (w - z))
        - (∮ w in C(z₀, ε), (f w - f z) / (w - z)) = 0 :=
    slope_integral_diff_radius_indep hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  have h_spl :
      (∮ w in C(z₀, r), f w / (w - z))
        - (∮ w in C(z₀, ε), f w / (w - z))
      = f z * ((∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹))
        + ((∮ w in C(z₀, r), (f w - f z) / (w - z))
            - (∮ w in C(z₀, ε), (f w - f z) / (w - z))) :=
    kernel_integral_linear_split hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  rw [h_spl, h_ker, h_slp]
  ring

end Problems.residue_thm
