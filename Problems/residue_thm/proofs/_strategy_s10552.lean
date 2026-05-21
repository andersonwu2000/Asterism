import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_glued_qmp_diff_at_pole
import Problems.residue_thm.proofs.L_glued_qmp_diff_off_a

namespace Problems.residue_thm

-- Split `Differentiable ℂ f` for `f w := if w = a then g a else Q w - P w` by
-- case-splitting on whether the input equals `a`:
--   * off `a`: locally `f = Q - P` on the open set `univ \ {a}`, where both
--     `Q` and `P` are analytic — `glued_qmp_diff_off_a` handles each `z ≠ a`.
--   * at `a`: locally `f = g` on `Metric.ball a R` via `h_diff_eq` plus the
--     definitional value at `a` — `glued_qmp_diff_at_pole` packages this.
-- Combinator: `Differentiable` unfolds to `∀ z, DifferentiableAt ⋯ z`, so we
-- introduce `z`, dispatch by `by_cases hz : z = a`, and quote each sub-goal.
theorem s10552
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_decay : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    Differentiable ℂ (fun w => if w = a then g a else Q w - P w)  := by
  intro z
  by_cases hz : z = a
  · have h_at_a : DifferentiableAt ℂ (fun w => if w = a then g a else Q w - P w) a :=
      glued_qmp_diff_at_pole hR hQ_an hP_an hg_an h_diff_eq
    simpa [hz] using h_at_a
  · exact glued_qmp_diff_off_a hR hQ_an hP_an hg_an h_diff_eq z hz

end Problems.residue_thm
