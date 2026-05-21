-- Pointwise Cauchy substitution (Q kernel) + Fubini swap + winding identification.
--   (1) `fubini_swap_circle_path_q` — swap order of ∫₀¹ and ∮ over C(a,ε) for the Q kernel.
--   (2) `inner_path_int_winding_q` — for w on sphere a ε,
--       ∫₀¹ γ'(t)/(w-γt) dt = -(2πi)·windingNumber γ a (winding constancy on disk).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10543

namespace Problems.residue_thm

def path_int_p_eq_winding_circle_int_q := @Problems.residue_thm.s10543

end Problems.residue_thm
