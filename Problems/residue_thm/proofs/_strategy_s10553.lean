import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct: the if-function agrees with (Q - P) off {a}, which is cocompact-eventually,
-- and (Q - P) → 0 by Tendsto.sub of hQ_decay, hP_decay; close via tendsto_congr'.
theorem s10553
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_decay : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    Filter.Tendsto (fun w => if w = a then g a else Q w - P w)
      (Filter.cocompact ℂ) (nhds 0)  := by
  have h_sub : Filter.Tendsto (fun w => Q w - P w) (Filter.cocompact ℂ) (nhds 0) := by
    simpa using hQ_decay.sub hP_decay
  have h_compact : IsCompact ({a} : Set ℂ) := isCompact_singleton
  have h_event : ∀ᶠ w in Filter.cocompact ℂ, w ∉ ({a} : Set ℂ) :=
    h_compact.compl_mem_cocompact
  have h_eq : (fun w => if w = a then g a else Q w - P w) =ᶠ[Filter.cocompact ℂ]
              (fun w => Q w - P w) := by
    filter_upwards [h_event] with w hw
    have hwa : w ≠ a := by simpa using hw
    simp [hwa]
  exact (Filter.tendsto_congr' h_eq).mpr h_sub

end Problems.residue_thm
