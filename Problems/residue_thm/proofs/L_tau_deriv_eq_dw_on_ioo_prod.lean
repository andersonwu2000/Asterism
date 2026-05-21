-- For x ∈ Ioo 0 1 and t ∈ Ioo 0 1, both `deriv ↔ derivWithin (Icc 0 1)` rewrites
-- are unconditional via `derivWithin_of_mem_nhds` (Icc ∈ nhds at interior points).
-- The inner `deriv (H τ'') t = derivWithin (H τ'') (Icc 0 1) t` rewrite makes the
-- two outer functions literally equal, then the outer rewrite at x finishes.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10350

namespace Problems.residue_thm

def tau_deriv_eq_dw_on_ioo_prod := @Problems.residue_thm.s10350

end Problems.residue_thm
