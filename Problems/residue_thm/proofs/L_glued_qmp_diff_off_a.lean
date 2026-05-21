import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- glued_qmp_diff_off_a: DifferentiableAt for the glued Q-P/g function at z ≠ a,
-- using AnalyticOn.differentiableOn + DifferentiableAt.congr_of_eventuallyEq on {a}ᶜ ∈ nhds z.
-- entry_kind: Builder
theorem glued_qmp_diff_off_a
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w)
    (z : ℂ) (hz : z ≠ a) :
    DifferentiableAt ℂ (fun w => if w = a then g a else Q w - P w) z := by
  have hz_mem : z ∈ Set.univ \ {a} := ⟨Set.mem_univ z, by simpa using hz⟩
  have hopen : IsOpen (Set.univ \ {a} : Set ℂ) := isOpen_univ.sdiff isClosed_singleton
  have hQ_diff : DifferentiableAt ℂ Q z :=
    hQ_an.differentiableOn.differentiableAt (hopen.mem_nhds hz_mem)
  have hP_diff : DifferentiableAt ℂ P z :=
    hP_an.differentiableOn.differentiableAt (hopen.mem_nhds hz_mem)
  have hQP_diff : DifferentiableAt ℂ (fun w => Q w - P w) z := hQ_diff.sub hP_diff
  have hne_nhd : ({a} : Set ℂ)ᶜ ∈ nhds z := isClosed_singleton.isOpen_compl.mem_nhds hz
  exact hQP_diff.congr_of_eventuallyEq (by
    filter_upwards [hne_nhd] with w hw
    have hwne : w ≠ a := by simpa using hw
    simp [hwne])

end Problems.residue_thm
