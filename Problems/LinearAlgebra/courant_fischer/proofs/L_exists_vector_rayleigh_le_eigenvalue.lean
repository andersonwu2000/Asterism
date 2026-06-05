-- Courant–Fischer upper bound: a nonzero x ∈ S with Rayleigh ≤ λ_k exists.
-- h_bottom (sub-goal): the bottom (n−k)-eigenvector subspace W has finrank n−k and
--   every nonzero vector in it has Rayleigh ≤ λ_k (the spectral content; drops S).
-- subspace_inter_nonzero (sub-goal, dedupes to the proved dimension-count brick):
--   finrank S + finrank W = (k+1)+(n−k) = n+1 > n forces a nonzero x ∈ S ⊓ W.
-- Combining, that x lies in W so hWbound bounds its Rayleigh by λ_k.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11619

namespace Problems.LinearAlgebra.courant_fischer

def exists_vector_rayleigh_le_eigenvalue := @Problems.LinearAlgebra.courant_fischer.s11619

end Problems.LinearAlgebra.courant_fischer
