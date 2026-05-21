-- Decompose parametric integral continuity into (i) joint continuity of the
-- integrand on `ball z r ×ˢ Icc 0 1` (uses `derivWithin γ` continuous on Icc
-- via `ContDiffOn.continuousOn_derivWithin`, plus `γ t - w ≠ 0` since γ avoids
-- ball z r and w ∈ ball z r), and (ii) a generic bridge transporting joint
-- ContinuousOn on `(open w-set) ×ˢ Icc 0 1` to ContinuousOn of the parametric
-- interval-integral on the w-set (pointwise DCT with constant bound from
-- compactness of `closedBall w₀ ρ ×ˢ Icc 0 1`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10612

namespace Problems.residue_thm

def param_int_dw_continuous_on_ball := @Problems.residue_thm.s10612

end Problems.residue_thm
