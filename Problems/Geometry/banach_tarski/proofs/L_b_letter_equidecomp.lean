-- Generator-1 analogue of `build_letter0_equidecomp`: the b-letter piece
-- `Wᵦ ∪ Wᵦ⁻¹` of M bijects onto M via id on `Wᵦ` ({head?=(1,true)}) and
-- φ(of 1) on `Wᵦ⁻¹` ({head?=(1,false)}).  Set A=Wᵦ (kept), B=Wᵦ⁻¹ (moved by
-- g0:=φ(of 1)); the piecewise self-map f (id/g0•·) with inverse g (id/g0⁻¹•·).
-- Sub-goals: `b_letter_pieces_disjoint` (A,B disjoint) and `b_letter_split`
-- (g0''B = M\A, the meaty image equality).  The generic PartialEquiv laws and
-- IsDecompOn witness are reused verbatim from the proved siblings
-- `letter0_partial_equiv_laws` / `letter0_is_decomp` (both abstract in A,B,g0,f,g).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11480

namespace Problems.Geometry.banach_tarski

def b_letter_equidecomp := @Problems.Geometry.banach_tarski.s11480

end Problems.Geometry.banach_tarski
