-- Decompose into one orthonormality sub-goal: the family `j ↦ σ_{j.val}⁻¹ • T(b_E ⟨j.val,_⟩)`
-- (or junk on indices ≥ finrank E), restricted to indices where j.val < finrank E ∧ σ ≠ 0,
-- is orthonormal in F. Patch applies `Orthonormal.exists_orthonormalBasis_extension_of_card_eq`
-- to extend this orthonormal partial family to an `OrthonormalBasis (Fin (finrank F)) 𝕜 F`,
-- then identifies `b_F ⟨i,h⟩ = σ_i⁻¹ • T(b_E i)` for σ_i ≠ 0 and rearranges to the goal shape.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10859

namespace Problems.LinearAlgebra.svd

def exists_b_f_apply_eq_nonzero := @Problems.LinearAlgebra.svd.s10859

end Problems.LinearAlgebra.svd
