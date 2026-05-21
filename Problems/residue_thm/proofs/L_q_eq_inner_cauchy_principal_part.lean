-- Apply the inner Cauchy integral construction (`inner_principal_part_step_wrapper`)
-- at radius 1 to obtain P with cocompact decay + the inner-Cauchy formula.
-- Supplement with `outer_holomorphic_step_wrapper` + `cauchy_annulus_step_wrapper`
-- to get a holomorphic remainder g with Q = g + P on Metric.ball a 1 \ {a}.
-- The Liouville sub-goal `q_eq_p_via_liouville` then promotes Q = P globally on ℂ \ {a}:
-- the difference Q - P extends analytically across a (via g), is bounded
-- (both decay at cocompact), hence is constantly zero by Liouville.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10536

namespace Problems.residue_thm

def q_eq_inner_cauchy_principal_part := @Problems.residue_thm.s10536

end Problems.residue_thm
