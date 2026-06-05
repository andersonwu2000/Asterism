-- Lower bound λ_k ≤ sSup via `le_csSup` with the top-(k+1)-eigenvector test subspace.
-- h_bdd (rayleigh_sup_set_bdd_above): the sSup set is bounded above (each member sInf
--   ≤ ‖T‖ by Cauchy–Schwarz), giving the `BddAbove` premise of `le_csSup`.
-- h_exists (exists_test_subspace_inf_ge_eigenvalue): a witness subspace S of finrank k+1
--   whose Rayleigh sInf is ≥ λ_k; it is a member of the sSup set, so λ_k ≤ sInf S ≤ sSup.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11621

namespace Problems.LinearAlgebra.courant_fischer

def eigenvalue_le_sup_inf_rayleigh := @Problems.LinearAlgebra.courant_fischer.s11621

end Problems.LinearAlgebra.courant_fischer
