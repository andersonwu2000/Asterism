-- d ∘ d = 0 for the test-form exterior derivative CLM.
-- `ContinuousLinearMap.ext` + `DFunLike.ext` (`ext f x v`) reduce CLM-equality
-- to a pointwise identity on underlying functions; `comp_apply`, `extDerivCLM`,
-- `postcompCLM_apply` and `fderivCLM_apply_of_le le_top` unfold both d-CLMs to
-- `alternatizeUncurryFinCLM ∘ fderiv ℝ`, which is defeq to `extDeriv`. The goal
-- becomes `extDeriv (extDeriv f) = 0`, closed by Mathlib's `extDeriv_extDeriv`
-- with `f.contDiff : ContDiff ℝ ⊤ f` and `minSmoothness ℝ 2 ≤ ∞`.
import Mathlib
import Problems.Geometry.derham_dd_zero.Defs
import Problems.Geometry.derham_dd_zero.proofs._strategy_s17778

namespace Problems.Geometry.derham_dd_zero

def main := @Problems.Geometry.derham_dd_zero.s17778

end Problems.Geometry.derham_dd_zero
