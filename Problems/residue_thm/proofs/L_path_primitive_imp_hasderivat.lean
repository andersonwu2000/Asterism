-- Straight-line segment trick: for each z ≠ a, use hF on γ_h(t)=z+t·h with
-- ‖h‖<dist z a to get F(z+h)-F z = ∫₀¹ Q(z+t·h)·h dt (h_seg), then combine
-- with continuity of Q at z (from hQ_an) to conclude HasDerivAt F (Q z) z.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10498

namespace Problems.residue_thm

def path_primitive_imp_hasderivat := @Problems.residue_thm.s10498

end Problems.residue_thm
