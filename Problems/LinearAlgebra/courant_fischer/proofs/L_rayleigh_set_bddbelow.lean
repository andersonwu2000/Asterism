-- BddBelow of the Rayleigh set: exhibit -C as a lower bound, where C bounds the
-- operator norm of T (finite-dim ⇒ T is bounded, cited inline via toContinuousLinearMap).
-- Sole sub-goal `rayleigh_ge_neg_bound` drops the set/sInf layer: for any nonzero x,
-- Cauchy–Schwarz + the operator bound give ⟪Tx,x⟫/‖x‖² ≥ -C.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11620

namespace Problems.LinearAlgebra.courant_fischer

def rayleigh_set_bddbelow := @Problems.LinearAlgebra.courant_fischer.s11620

end Problems.LinearAlgebra.courant_fischer
