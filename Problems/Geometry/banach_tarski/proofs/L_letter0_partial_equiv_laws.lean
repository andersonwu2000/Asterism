-- The four PartialEquiv laws for the letter-0 piece: f = id on A / g0•· off A,
-- g = id on A / g0⁻¹•· off A.
-- Direct case split on A vs B using only: hsplit (g0•B = M\A), Disjoint A B, A ⊆ M, and the
-- group-action laws inv_smul_smul / smul_inv_smul. No nontrivial sub-claim — ships as a leaf.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11481

namespace Problems.Geometry.banach_tarski

def letter0_partial_equiv_laws := @Problems.Geometry.banach_tarski.s11481

end Problems.Geometry.banach_tarski
