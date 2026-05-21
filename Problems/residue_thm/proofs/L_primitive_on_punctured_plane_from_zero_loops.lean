-- Morera-style construction of a primitive on ℂ \ {a} from closed-loop-zero.
-- (S1) Path-integral form of F: build F : ℂ → ℂ such that for any C¹ path γ in
--      ℂ \ {a}, F(γ 1) - F(γ 0) = ∫₀¹ Q(γ t) · γ' dt. Uses h_loops via path
--      concatenation/reverse to establish path-independence.
-- (S2) Path-integral equation ⇒ HasDerivAt: for z ≠ a, the straight-line
--      segment γ(t) = z + t·h (with |h| < dist(z,a)) gives F(z+h) - F(z) ≈
--      Q(z)·h via continuity of Q at z, yielding HasDerivAt F (Q z) z.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10489

namespace Problems.residue_thm

def primitive_on_punctured_plane_from_zero_loops := @Problems.residue_thm.s10489

end Problems.residue_thm
