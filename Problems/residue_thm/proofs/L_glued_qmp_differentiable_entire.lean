-- Split `Differentiable ℂ f` for `f w := if w = a then g a else Q w - P w` by
-- case-splitting on whether the input equals `a`:
--   * off `a`: locally `f = Q - P` on the open set `univ \ {a}`, where both
--     `Q` and `P` are analytic — `glued_qmp_diff_off_a` handles each `z ≠ a`.
--   * at `a`: locally `f = g` on `Metric.ball a R` via `h_diff_eq` plus the
--     definitional value at `a` — `glued_qmp_diff_at_pole` packages this.
-- Combinator: `Differentiable` unfolds to `∀ z, DifferentiableAt ⋯ z`, so we
-- introduce `z`, dispatch by `by_cases hz : z = a`, and quote each sub-goal.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10552

namespace Problems.residue_thm

def glued_qmp_differentiable_entire := @Problems.residue_thm.s10552

end Problems.residue_thm
