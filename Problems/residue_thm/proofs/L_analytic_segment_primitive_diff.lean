-- Decompose primitive-with-FTC bundle into (a) primitive existence on the ball
-- from `hf` alone, and (b) FTC along the C¹ sub-path on `Icc a b` given any
-- such primitive. Combinator pairs the obtained primitive `F` with its FTC
-- equation. Sub-goal (a) is a one-liner via Mathlib `DifferentiableOn.isExactOn_ball`;
-- sub-goal (b) is the proved sibling shape `path_int_eq_diff_on_ball_subinterval`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10540

namespace Problems.residue_thm

def analytic_segment_primitive_diff := @Problems.residue_thm.s10540

end Problems.residue_thm
