-- Build the "first letter is generator 0" Equidecomp piece of M.
-- Split S₀ = {x∈M | word head sits at generator 0} into a-words A and a⁻¹-words B
-- (letter0_source_eq_union, letter0_pieces_disjoint). The piecewise map f = id on A,
-- φ(of 0)•· on B realizes the F₂ identity Wₐ ⊔ a·Wₐ⁻¹ = F₂, so its image is all of M;
-- the only genuine-math brick is the set identity g0•B = M\A (letter0_split).
-- The four PartialEquiv laws (letter0_partial_equiv_laws) and the finite-piece
-- decomposition (letter0_is_decomp) are abstract over f,g,A,B,g0.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11472

namespace Problems.Geometry.banach_tarski

def build_letter0_equidecomp := @Problems.Geometry.banach_tarski.s11472

end Problems.Geometry.banach_tarski
