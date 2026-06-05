-- Witness subspace S = span of the top (k+1) eigenvectors {e_0,…,e_k}.
-- Three sub-goals: (1) finrank S = k+1; (2) the Rayleigh set is nonempty;
-- (3) every nonzero x ∈ S has Rayleigh ≥ λ_k (heart: λ_i ≥ λ_k for i ≤ k by
-- antitone, expand numerator in the eigenbasis).  Then le_csInf glues (2)+(3)
-- into λ_k ≤ sInf, and S, (1) discharge the existential.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11623

namespace Problems.LinearAlgebra.courant_fischer

def exists_test_subspace_inf_ge_eigenvalue := @Problems.LinearAlgebra.courant_fischer.s11623

end Problems.LinearAlgebra.courant_fischer
