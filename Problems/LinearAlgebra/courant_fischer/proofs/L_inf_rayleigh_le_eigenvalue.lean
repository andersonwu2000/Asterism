-- Courant–Fischer upper bound (per fixed (k+1)-dim S): the inner Rayleigh sInf ≤ λ_k.
-- A dimension count yields a nonzero x ∈ S landing in the bottom eigenspace with
-- Rayleigh ≤ λ_k (h_exists); since that Rayleigh value lies in the bounded-below set
-- (h_bdd), csInf_le + transitivity closes the goal. Both sub-goals drop the sInf layer.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11618

namespace Problems.LinearAlgebra.courant_fischer

def inf_rayleigh_le_eigenvalue := @Problems.LinearAlgebra.courant_fischer.s11618

end Problems.LinearAlgebra.courant_fischer
