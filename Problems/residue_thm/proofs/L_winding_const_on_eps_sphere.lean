-- For w on the ε-sphere around a:
-- (1) `eps_bump_radius_avoiding_path` (Builder, compactness): there exists r > ε
--     such that γ still avoids the closed r-ball around a, so w sits strictly
--     inside the open r-ball.
-- (2) `winding_const_on_open_ball_off_image` (Backward, locally-constant winding):
--     when γ avoids the closed r-ball around z, windingNumber γ is constant on
--     the open r-ball, equal to windingNumber γ z. Apply with z = a.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10569

namespace Problems.residue_thm

def winding_const_on_eps_sphere := @Problems.residue_thm.s10569

end Problems.residue_thm
