-- Build ψ := FreeGroup.lift g, where g : Fin 2 → (E ≃ₗᵢ[ℝ] E) are the two rotation
-- generators realized through a monoid hom `mat` to 3×3 matrices (the SO(3) embedding).
-- so3_realization_hom supplies g, mat (injective, det-preserving) with mat(g i)/(mat(g i))⁻¹
-- equal to the four concrete generator matrices. Then per nontrivial word w:
--   • det = 1: mat preserves det and every generator-matrix has det 1  (lift_det_one)
--   • ψ w ≠ refl(=1): the matrix word-product ≠ 1 (rotation_word_ne_one_of_reduced, s11407)
--     transported back through injectivity of mat  (lift_ne_one)
-- injectivity of ψ is the same ne-one fact via injective_iff_map_eq_one.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11478

namespace Problems.Geometry.banach_tarski

def free_so3_embedding := @Problems.Geometry.banach_tarski.s11478

end Problems.Geometry.banach_tarski
