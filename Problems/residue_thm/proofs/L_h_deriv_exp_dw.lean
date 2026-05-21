-- Chain-rule decomposition for `exp(-G(s))` where `G(s) = ∫₀ˢ deriv γ t / (γ t - a)`.
-- Sub-goal `h_deriv_integral_dw`: FTC for the integral, output derivative is
-- `derivWithin γ (Icc 0 1) s / (γ s - a)` (uses derivWithin, not deriv, to match
-- the parent's strategy s10311 — avoids the s10307 junk-at-endpoints issue).
-- Closer: `.neg.cexp` produces `exp(-G(s)) * -(derivWithin γ (Icc 0 1) s / (γ s - a))`;
-- `mul_comm` aligns with the target derivative shape.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10312

namespace Problems.residue_thm

def h_deriv_exp_dw := @Problems.residue_thm.s10312

end Problems.residue_thm
