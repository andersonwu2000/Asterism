-- Courant–Fischer upper bound: sSup over (k+1)-dim subspaces of the inner sInf
-- Rayleigh quotient is ≤ eigenvalue k. Closed by `csSup_le`:
--   • h_exists (exists_subspace_finrank): the index set is nonempty — some (k+1)-dim
--     subspace exists, so the sSup has a witness `r`.
--   • h_inf (inf_rayleigh_le_eigenvalue): for EVERY (k+1)-dim S, the inner sInf of the
--     Rayleigh set is ≤ eigenvalue k (dimension count yields a nonzero vector in
--     S meeting the bottom-(n−k) eigenspace, whose Rayleigh quotient is ≤ λ_k).
-- Both sub-goals drop the outer sSup layer, hence are strictly simpler.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11617

namespace Problems.LinearAlgebra.courant_fischer

def sup_inf_rayleigh_le_eigenvalue := @Problems.LinearAlgebra.courant_fischer.s11617

end Problems.LinearAlgebra.courant_fischer
