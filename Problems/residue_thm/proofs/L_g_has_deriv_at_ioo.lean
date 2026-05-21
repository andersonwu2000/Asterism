-- Decompose `dG/dt = X` at `(τ, t) ∈ Ico × Ioo` into:
-- (1) `f_section_chain_rule` — chain rule for `t' ↦ f(H τ t')` at interior `t`.
-- (2) `partial_tau_has_deriv_in_t` — Schwarz mixed-partial:
--     `t' ↦ ∂_{τ'} H(τ, t')` has `t`-derivative `∂_{τ'} ∂_t H(τ, t)`.
-- (3) `derivwithin_section_product_chain_eq` — derivWithin product+chain
--     rule equating the `HasDerivAt.mul` output to the parent's `derivWithin` form.
-- Combine (1) and (2) via `HasDerivAt.mul`, then rewrite the value with (3).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10339

namespace Problems.residue_thm

def g_has_deriv_at_ioo := @Problems.residue_thm.s10339

end Problems.residue_thm
