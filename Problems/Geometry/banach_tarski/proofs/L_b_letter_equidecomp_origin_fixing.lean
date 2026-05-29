-- Origin-fixing refinement of b_letter_equidecomp (s11480): generator-1 piecewise map
-- (f = id on A=Wᵦ, g0•· on B=Wᵦ⁻¹, g0 = φ(of 1)) reconstructed inline from the proved
-- bricks (b_letter_split, b_letter_pieces_disjoint, letter0_partial_equiv_laws), now ALSO
-- exposing the realizing Finset Sb = {1, g0} and proving every element fixes 0 (1 0 = 0;
-- g0 0 = φ(of 1) 0 = 0 via hfix0).  No new sub-goals — leaf reconstruction.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11528

namespace Problems.Geometry.banach_tarski

def b_letter_equidecomp_origin_fixing := @Problems.Geometry.banach_tarski.s11528

end Problems.Geometry.banach_tarski
