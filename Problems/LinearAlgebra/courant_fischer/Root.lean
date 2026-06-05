-- Courant–Fischer max-min equality, proved by `le_antisymm` over two bounds.
-- h_lower (sub-goal A): eigenvalue k ≤ sSup, via the top-(k+1)-eigenvector test
--   subspace S₀ where every Rayleigh quotient ≥ eigenvalue k.
-- h_upper (sub-goal B): sSup ≤ eigenvalue k, via any (k+1)-dim S meeting the
--   bottom-(n−k)-eigenvector subspace in a nonzero x with Rayleigh ≤ eigenvalue k.
-- Each bound is a standalone theorem re-declaring all binders; both rely on the
-- proved bricks rayleigh_numerator_eigenbasis / subspace_inter_nonzero_of_finrank.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11615

namespace Problems.LinearAlgebra.courant_fischer

def main := @Problems.LinearAlgebra.courant_fischer.s11615

end Problems.LinearAlgebra.courant_fischer
