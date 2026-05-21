-- Cauchy on a ball via primitive existence on a disk + FTC along a closed C¹ path.
-- (1) `DifferentiableOn.isExactOn_ball` (Mathlib) gives a primitive `F` of `f` on the ball;
-- (2) sub-goal `path_integral_eq_diff_on_ball` rewrites the path integral as `F(γ 1) − F(γ 0)`
--     (specialization of the proved `path_integral_eq_primitive_diff` with `U := ball z₀ R`);
-- (3) `hclosed` collapses the difference to `0`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10400

namespace Problems.residue_thm

def closed_path_integral_zero_on_ball := @Problems.residue_thm.s10400

end Problems.residue_thm
