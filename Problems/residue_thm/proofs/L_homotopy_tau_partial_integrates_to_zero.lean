-- Strategy: rewrite `deriv` as `derivWithin (Icc 0 1)` under the integral (Icc 0 1 ∈ 𝓝 τ for
-- τ ∈ Ioo), reduce via sibling `integral_tau_partial_eq_boundary` to the boundary difference
-- `f(H τ 1)·∂τ H(·,1) − f(H τ 0)·∂τ H(·,0)`, and conclude 0 via `boundary_partials_vanish`
-- (hH0/hH1 force `τ' ↦ H τ' 0` and `τ' ↦ H τ' 1` constant on Icc, so derivWithin vanishes).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10333

namespace Problems.residue_thm

def homotopy_tau_partial_integrates_to_zero := @Problems.residue_thm.s10333

end Problems.residue_thm
