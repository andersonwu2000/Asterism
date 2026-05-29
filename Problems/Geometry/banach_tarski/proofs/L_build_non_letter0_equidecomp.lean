-- Two-piece partition of M by "first letter is generator 0?": this is the
-- NON-letter-0 piece = {empty word} ∪ Wᵦ ∪ Wᵦ⁻¹.  Unlike the letter-0 piece,
-- its source carries one extra orbit-point per orbit (the representative, whose
-- word is empty / head? = none), so the naive id/φ(of 1) split cannot biject it
-- onto M (Wᵦ ⊔ φ(of 1)•Wᵦ⁻¹ already = M).  Factor as a Hilbert-hotel absorption
-- `absorb_empty_word` (full source ≅ the plain b-block Sᵦ, swallowing the reps
-- along the φ(of 1)⁻¹ tower) composed with the clean single-generator block
-- `b_letter_equidecomp` (Sᵦ ≅ M, the exact analogue of the letter-0 builder for
-- generator 1).  `equidecomp_trans_glue` packages `Equidecomp.trans` when the
-- middle target/source agree.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11473

namespace Problems.Geometry.banach_tarski

def build_non_letter0_equidecomp := @Problems.Geometry.banach_tarski.s11473

end Problems.Geometry.banach_tarski
