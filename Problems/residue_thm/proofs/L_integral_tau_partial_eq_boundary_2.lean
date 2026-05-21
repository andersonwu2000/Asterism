-- FTC in `t` against the antiderivative `G(t) := f(H τ t) · ∂_τ' H(τ', t)|_{τ'=τ}`.
-- The integrand `X(t) := ∂_τ' (f(H τ' t) · ∂_t H(τ', t))|_{τ'=τ}` equals `dG/dt` on the
-- interior via the product rule + Schwarz (`H` is C²), giving
-- `∫₀¹ X = G 1 - G 0 = f(H τ 1)·∂_τ' H(·,1) − f(H τ 0)·∂_τ' H(·,0)`.
-- Sub-goals: (1) `g_continuous_on_icc` — antiderivative continuous on `Icc 0 1`;
-- (2) `g_has_deriv_at_ioo` — Schwarz/chain rule interior identity `dG/dt = X` on `Ioo 0 1`;
-- (3) `x_interval_integrable` — integrand interval-integrable on `[0,1]`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10335

namespace Problems.residue_thm

def integral_tau_partial_eq_boundary_2 := @Problems.residue_thm.s10335

end Problems.residue_thm
