-- Rayleigh numerator in the eigenbasis: expand ⟪Tx,x⟫ over the orthonormal
-- eigenbasis via `sum_inner_mul_inner`; each cross term ⟪Tx,bᵢ⟫·⟪bᵢ,x⟫ reduces
-- (sub-goal `inner_Tx_eigenvector`) to λᵢ·(repr x i), giving λᵢ·(repr x i)².
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11614

namespace Problems.LinearAlgebra.courant_fischer

def rayleigh_numerator_eigenbasis := @Problems.LinearAlgebra.courant_fischer.s11614

end Problems.LinearAlgebra.courant_fischer
