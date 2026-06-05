-- For x in the top-(k+1) eigenvector span S, the Rayleigh quotient ≥ λ_k.
-- Decouple into: (1) components of x outside the top (k+1) eigendirections
-- vanish (pure geometry of S); (2) with those vanishing, the eigenbasis
-- expansion gives the numerator bound λ_k·‖x‖² ≤ ⟪Tx,x⟫ (antitone spectrum).
-- Divide by ‖x‖² > 0 (x ≠ 0) to close.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11627

namespace Problems.LinearAlgebra.courant_fischer

def rayleigh_ge_on_topeig := @Problems.LinearAlgebra.courant_fischer.s11627

end Problems.LinearAlgebra.courant_fischer
