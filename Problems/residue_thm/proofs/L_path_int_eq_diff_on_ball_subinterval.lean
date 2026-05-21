-- FTC along a C¹ path inside a ball: F primitive on ball ⇒ ∫ f(γ)·γ' = F(γ b) − F(γ a).
-- Splits via `intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le hab` into
--   (a) ContinuousOn (F ∘ γ) on Icc a b,
--   (b) chain rule HasDerivAt (F ∘ γ) at every x ∈ Ioo a b (interior unlocks DifferentiableAt
--       since Icc a b ∈ 𝓝 x, sidestepping the derivWithin/junk-endpoint trap),
--   (c) IntervalIntegrable (fun t => f (γ t) * deriv γ t) on a..b.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10534

namespace Problems.residue_thm

def path_int_eq_diff_on_ball_subinterval := @Problems.residue_thm.s10534

end Problems.residue_thm
