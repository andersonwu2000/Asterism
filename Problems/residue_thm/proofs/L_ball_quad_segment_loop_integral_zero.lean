-- Telescoping primitive-difference along the closed quadrilateral z₁→z₂→z₃→z₄→z₁.
-- DifferentiableOn ℂ f on a ball gives a primitive F via `hf.isExactOn_ball`
-- (Mathlib `DifferentiableOn.isExactOn_ball`); each straight-line segment integral
-- collapses to `F(end) − F(start)` by FTC along the linear path inside the convex
-- ball, so the 4-cycle telescopes to `F z₁ − F z₁ = 0`. Single sub-goal
-- `segment_integral_eq_primitive_diff_in_ball` packages "primitive ⇒ segment
-- integral = primitive difference" once and is then applied 4 times.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10619

namespace Problems.residue_thm

def ball_quad_segment_loop_integral_zero := @Problems.residue_thm.s10619

end Problems.residue_thm
