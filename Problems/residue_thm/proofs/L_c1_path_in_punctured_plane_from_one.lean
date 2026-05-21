-- Construct γ(t) = ((1-t) + t·‖w‖) · exp(i·t·arg w) — a C¹ polar interpolation
-- from 1 to w whose modulus stays positive away from 0.
-- Sub-goals: (a) smoothness of the explicit formula, (b) modulus 1-t+t·‖w‖ > 0
-- on Icc 0 1 (since both endpoints 1 and ‖w‖ are positive when w ≠ 0).
-- Endpoint equalities γ(0)=1 and γ(1)=w discharge inline via simp and
-- Complex.norm_mul_exp_arg_mul_I; non-vanishing combines (b) with Complex.exp_ne_zero.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10545

namespace Problems.residue_thm

def c1_path_in_punctured_plane_from_one := @Problems.residue_thm.s10545

end Problems.residue_thm
