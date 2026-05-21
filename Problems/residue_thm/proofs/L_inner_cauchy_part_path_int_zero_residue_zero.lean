-- Pick ε > 0 separating γ from a (uniform) and also satisfying ε < R, so
-- hP_rep is applicable along γ with the same ε. Reduce ∫₀¹ P(γt)·γ'(t) dt to
-- winding γ a · ∮_{C(a,ε)} Q via Fubini-swap + winding-locally-constant on the
-- inner circle, then evaluate ∮ Q over C(a,ε) as 2πi · residue Q a (radius
-- independence of the residue-defining circle); hQ_res = 0 collapses to 0.
-- Sub-goals:
--   (1) uniform_eps_separation_path_radius — Builder: compactness of γ([0,1])
--       supplies a uniform separation ε; min with R/2 keeps ε < R.
--   (2) path_int_p_eq_winding_circle_int_q — Backward: Fubini-swap circle/path
--       + windingNumber γ w constant on ball a ε.
--   (3) circle_int_q_eq_two_pi_residue_at — Builder: existing toolkit pattern
--       (cf. circle_int_eq_two_pi_residue) on Q analytic on punctured plane.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10535

namespace Problems.residue_thm

def inner_cauchy_part_path_int_zero_residue_zero := @Problems.residue_thm.s10535

end Problems.residue_thm
