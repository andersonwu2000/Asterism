-- Split into two siblings:
--   (A) `t_b_e_zero_of_sigma_zero` (Builder): σ_i = 0 ⇒ T(b_E i) = 0, from h_inner with j=i.
--   (B) `exists_b_f_apply_eq_nonzero` (Backward): orthonormal-extension construction,
--       restricted to the apply equation when σ_i ≠ 0.
-- Closer fuses (A)+(B): low-index branch splits on σ_i; σ_i=0 makes both sides 0 via (A),
-- σ_i≠0 uses (B); high-index branch uses h_zero via `dif_neg`.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10858

namespace Problems.LinearAlgebra.svd

def exists_b_f_apply_eq_dite_with_zero := @Problems.LinearAlgebra.svd.s10858

end Problems.LinearAlgebra.svd
