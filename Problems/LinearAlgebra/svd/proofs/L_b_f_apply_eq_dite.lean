-- Split into (A) `t_apply_eigenbasis_zero_high`: T(b_E i) = 0 for indices
-- i with (i:ℕ) ≥ finrank F, derived from h_inner (giving ‖T(b_E i)‖² = σ_i²)
-- combined with the rank ≤ codimension bound forcing σ_i = 0 there, and
-- (B) `exists_b_f_apply_eq_dite_with_zero`: the main b_F existence assuming
-- that zero fact as a hypothesis. (A) is a single-equation kernel fact;
-- (B) absorbs all orthonormal-extension construction work and merely uses
-- the zero hypothesis to close the dite "else" branch directly.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10856

namespace Problems.LinearAlgebra.svd

def b_f_apply_eq_dite := @Problems.LinearAlgebra.svd.s10856

end Problems.LinearAlgebra.svd
