-- Q := P − r/(·−a) (r := residue P a) is analytic on ℂ\{a} with residue 0 at a,
-- so the parent contour integral collapses by FTC once a primitive of Q on ℂ\{a}
-- exists. Sub-goal (1) `punctured_primitive_subtracted` (Backward) builds that
-- primitive (carries the analytic content: Laurent decay of P at a + entire
-- antiderivative of the negative-Laurent tail). Sub-goal (2)
-- `closed_path_zero_from_punctured_primitive` (Builder) is the FTC closer:
-- given primitive F on ℂ\{a}, γ closed C¹ in ℂ\{a}, applies
-- `path_integral_eq_primitive_diff` (proved sibling on the open set ℂ\{a}) to
-- get F(γ 1) − F(γ 0), then `hclosed` collapses to 0.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10478

namespace Problems.residue_thm

def residue_subtracted_path_int_zero := @Problems.residue_thm.s10478

end Problems.residue_thm
