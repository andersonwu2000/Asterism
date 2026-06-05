-- BddAbove of the outer Courant–Fischer set {sInf(Rayleigh S) : finrank S = k+1}.
-- Upper bound = C, where ‖T x‖ ≤ C‖x‖ (operator bound, cited inline via toContinuousLinearMap).
-- For each S: exists_nonzero_mem_of_finrank_pos gives a nonzero x ∈ S (finrank = k+1 > 0);
-- rayleigh_le_bound bounds its Rayleigh quotient ≤ C; rayleigh_bddbelow_for_subspace gives
-- BddBelow, so csInf_le_of_le pushes sInf(Rayleigh S) ≤ (that quotient) ≤ C.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11624

namespace Problems.LinearAlgebra.courant_fischer

def rayleigh_sup_set_bdd_above := @Problems.LinearAlgebra.courant_fischer.s11624

end Problems.LinearAlgebra.courant_fischer
