-- Principal-part decomposition route (strategist directive): split `f` on `U \ T` as
-- `g + ∑ P_a` via the already-proved `analytic_remainder_principal_part_decomp`
-- (wrapped as a Builder sub-goal so the framework auto-imports it — direct
-- citation of a proved sibling fails lake build per LESSONS line 26), vanish the
-- analytic remainder integral, and apply the per-pole winding-residue formula.
-- Sub-goals:
--  (1) `principal_part_split_wrapper` (Builder, leaf wrapper) — re-exports the
--      proved `analytic_remainder_principal_part_decomp` (s10453).
--  (2) `analytic_remainder_path_integral_zero` — for `g` analytic on the
--      simply-connected open `U`, closed C¹ `γ` in `U`:
--      `∫₀¹ g(γ t)·γ'(t) dt = 0`. (Approach hint: compactness of `γ([0,1])` +
--      finite ball cover ⊂ `U` + per-ball `closed_path_integral_zero_on_ball`
--      after subdivision, sidestepping the C² null-homotopy obstruction.)
--  (3) `principal_part_winding_residue_step` — for `P` analytic on `ℂ \ {a}`
--      with `P → 0` at cocompact, closed C¹ `γ` avoiding `a`:
--      `∫₀¹ P(γ t)·γ'(t) dt = 2πi · (windingNumber γ a) · residue P a`.
-- Combinator: apply (1) for the integral split, rewrite the remainder integral via
-- (2), rewrite each pole integral via (3), then use `residue (P a) a = residue f a`
-- from (1) and `Finset.mul_sum` to assemble the right-hand side.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10473

namespace Problems.residue_thm

def main := @Problems.residue_thm.s10473

end Problems.residue_thm
