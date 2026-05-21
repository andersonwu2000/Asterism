-- Cauchy two-radius Laurent-style split: outer Cauchy integral on radius `r > dist z z₀`
-- defines `g` analytic on `ball z₀ R`; inner Cauchy integral on radius `ε < dist z z₀`
-- defines `P` analytic on `ℂ \ {z₀}` with `P → 0` at ∞; the annular Cauchy formula on
-- the punctured ball glues them as `f z = g z + P z`.
--   * `outer_holomorphic_part_exists`: witnesses `g` via the outer-circle integral; analytic
--     by parametric Cauchy + radius-independence on the punctured ball.
--   * `inner_principal_part_exists`: witnesses `P` via the inner-circle integral; analytic
--     on the open complement of `{z₀}` and tendsto zero at infinity by `|f(w)|`-bound on
--     each fixed inner circle.
--   * `cauchy_annulus_sum_formula`: from the two value-equations on annular `r`,`ε`,
--     applies the Mathlib Cauchy-Goursat / Cauchy integral formula on the annulus to get
--     `f z = g z + P z` on the punctured ball.
-- Each sub-goal drops one of the three responsibilities (outer existence, inner
-- existence + asymptotics, glueing identity) so is strictly simpler than the joint
-- existential of the parent.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10409

namespace Problems.residue_thm

def principal_part_extraction_at_singularity := @Problems.residue_thm.s10409

end Problems.residue_thm
