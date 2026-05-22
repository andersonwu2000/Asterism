-- Decompose into (A) constructing b_F : OrthonormalBasis of F packaging the
-- orthonormal-extension construction, with per-index dite-form column property
-- (T(b_E i) = σ_i • b_F⟨i,_⟩ when (i:ℕ) < finrank F, else 0), and (B) a purely
-- algebraic identity collapsing the indicator-shaped sum to that dite. (A) absorbs
-- all geometric/construction work; (B) is T,b_E,h_inner-independent Finset.sum
-- manipulation. Combinator rewrites the parent sum via (B), then closes by (A).
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10855

namespace Problems.LinearAlgebra.svd

def exists_b_f_apply_eq := @Problems.LinearAlgebra.svd.s10855

end Problems.LinearAlgebra.svd
