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
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10420

namespace Problems.residue_thm

def annulus_residue_diff := @Problems.residue_thm.s10420

end Problems.residue_thm
