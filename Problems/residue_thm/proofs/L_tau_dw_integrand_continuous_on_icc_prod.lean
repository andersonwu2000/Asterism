-- Reduce τ-`derivWithin` of the product `f∘H · ∂_t H` to the partial of the
-- joint function `g(q) = f(H q.1 q.2) · fderivWithin (H ·.1 ·.2) at (q,(0,1))`
-- applied in direction (1,0). `tau_dw_eq_fderiv_apply_on_icc_prod` provides the
-- pointwise equality on `Icc×Icc`; `fderiv_apply_continuous_on_icc_prod` gives
-- joint continuity of that smooth side. `ContinuousOn.congr` transports.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10357

namespace Problems.residue_thm

def tau_dw_integrand_continuous_on_icc_prod := @Problems.residue_thm.s10357

end Problems.residue_thm
