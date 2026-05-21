import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct: on `Metric.ball a R` the glued function equals `g` (uses `h_diff_eq`
-- off `a` and matches by definition at `a`), so it inherits differentiability
-- at `a` from `hg_an` via `Filter.EventuallyEq.differentiableAt_iff`.
theorem s10565
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    DifferentiableAt ℂ (fun w => if w = a then g a else Q w - P w) a  := by
  have hg_diff : DifferentiableAt ℂ g a :=
    hg_an.differentiableOn.differentiableAt (Metric.ball_mem_nhds a hR)
  have heq : (fun w => if w = a then g a else Q w - P w) =ᶠ[nhds a] g := by
    filter_upwards [Metric.ball_mem_nhds a hR] with w hw
    by_cases hwa : w = a
    · simp [hwa]
    · simp [hwa]; exact h_diff_eq w ⟨hw, hwa⟩
  exact (Filter.EventuallyEq.differentiableAt_iff heq).mpr hg_diff

end Problems.residue_thm
