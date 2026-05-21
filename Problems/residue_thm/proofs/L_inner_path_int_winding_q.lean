-- For w on the ε-sphere around a (and γ avoiding the closed ε-disk around a):
--   (A) `path_int_eq_neg_winding_at_w` — turn ∫ γ'/(w - γt) into -(2πi)·(windingNumber γ w)
--       via winding_integral_formula at w plus the sign flip 1/(w-γt) = -1/(γt-w).
--   (B) `winding_const_on_eps_sphere` — windingNumber γ w = windingNumber γ a for
--       w on the ε-sphere (winding constancy on the connected ε-disk that γ avoids).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10558

namespace Problems.residue_thm

def inner_path_int_winding_q := @Problems.residue_thm.s10558

end Problems.residue_thm
