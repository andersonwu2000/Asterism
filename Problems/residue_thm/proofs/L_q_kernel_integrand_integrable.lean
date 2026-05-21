-- Integrability of the Q-kernel on `Ioc 0 1 × Ioc 0 (2π)` via continuity on a compact set
-- with an auxiliary integrand using `derivWithin γ (Icc 0 1)` (continuous on `Icc 0 1`)
-- in place of the possibly-junk `deriv γ`, then transferring via a.e. equality.
--   (1) `q_kernel_aux_continuous_on_icc` — the auxiliary uncurried integrand (using
--       `derivWithin γ (Icc 0 1)` instead of `deriv γ`) is `ContinuousOn`
--       `Icc 0 1 ×ˢ Icc 0 (2π)`; on a compact set this yields `IntegrableOn`.
--   (2) `q_kernel_deriv_eq_derivWithin_ae_prod` — original and auxiliary integrands
--       agree a.e. on the product measure (they coincide on `Ioo 0 1 × Ioc 0 (2π)`,
--       whose complement in `Ioc 0 1 × Ioc 0 (2π)` is `{1} × Ioc 0 (2π)`, measure 0).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10584

namespace Problems.residue_thm

def q_kernel_integrand_integrable := @Problems.residue_thm.s10584

end Problems.residue_thm
