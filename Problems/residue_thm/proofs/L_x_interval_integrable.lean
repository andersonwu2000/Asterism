-- Reduce IntervalIntegrable to ContinuousOn (Icc 0 1) on a "clean" integrand that uses
-- `derivWithin (H τ') (Icc 0 1) t` instead of `deriv (H τ') t`, then transfer via congr_ae.
-- Sub-goals: (1) `x_clean_continuous_on_icc` — clean integrand is continuous on `Icc 0 1`;
-- (2) `x_clean_eq_orig_ae` — clean ≡ original a.e. on `uIoc 0 1` (they agree on `Ioo 0 1`
-- since `derivWithin (H τ') (Icc 0 1) t = deriv (H τ') t` for `t ∈ Ioo 0 1`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10340

namespace Problems.residue_thm

def x_interval_integrable := @Problems.residue_thm.s10340

end Problems.residue_thm
