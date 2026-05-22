-- Decompose into (A) existence of an orthonormal basis b_F of F such that
-- T(b_E i) expands as the i-th column of the target diagonal matrix in b_F
-- (the orthonormal-extension construction, using h_inner), and (B) a purely
-- mechanical translation from the column-expansion characterisation to the
-- toMatrix equality. (B) is a basis-representation unfolding free of any
-- geometry; (A) absorbs the construction work without needing the matrix
-- machinery, so each sub-goal is strictly simpler than the parent.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10854

namespace Problems.LinearAlgebra.svd

def exists_b_f_with_matrix_diag := @Problems.LinearAlgebra.svd.s10854

end Problems.LinearAlgebra.svd
