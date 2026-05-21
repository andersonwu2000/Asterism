import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_glued_qmp_differentiable_entire
import Problems.residue_thm.proofs.L_glued_qmp_tendsto_cocompact_zero

namespace Problems.residue_thm

-- Liouville bootstrap on the explicit gluing `h_ext z := if z = a then g a else Q z - P z`.
-- Sub-goal `glued_qmp_differentiable_entire` proves h_ext is entire; sub-goal
-- `glued_qmp_tendsto_cocompact_zero` proves it vanishes at ∞.
-- Liouville's `Differentiable.apply_eq_of_tendsto_cocompact` then forces h_ext ≡ 0,
-- and off `a` we have h_ext z = Q z - P z, giving Q z = P z.
theorem s10544
    {Q P : ℂ → ℂ} {a : ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hP_an : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_decay : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hg_an : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q w - P w = g w) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), Q z = P z  := by
  set h_ext : ℂ → ℂ := fun w => if w = a then g a else Q w - P w with hh_ext
  have h_diff : Differentiable ℂ h_ext :=
    glued_qmp_differentiable_entire hR hQ_an hQ_decay hP_an hP_decay hg_an h_diff_eq
  have h_decay : Filter.Tendsto h_ext (Filter.cocompact ℂ) (nhds 0) :=
    glued_qmp_tendsto_cocompact_zero hR hQ_an hQ_decay hP_an hP_decay hg_an h_diff_eq
  intro z hz
  have hz_ne : z ≠ a := by
    intro h
    exact hz.2 (by simp [h])
  have h_zero : h_ext z = 0 := h_diff.apply_eq_of_tendsto_cocompact z h_decay
  have h_ext_eq : h_ext z = Q z - P z := by
    simp [hh_ext, hz_ne]
  have hsub : Q z - P z = 0 := by rw [← h_ext_eq]; exact h_zero
  exact sub_eq_zero.mp hsub

end Problems.residue_thm
