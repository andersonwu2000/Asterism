import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cocompact_decay_of_diff_extension
import Problems.residue_thm.proofs.L_entire_extension_of_diff

namespace Problems.residue_thm

-- Liouville bootstrap: glue Q1 - Q2 across `a` using g to get an entire
-- function that decays at cocompact, then apply Liouville (via
-- `Differentiable.apply_eq_of_tendsto_cocompact`) to conclude it is 0.
theorem s10470
    {a : ℂ} {Q1 Q2 : ℂ → ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ1 : AnalyticOn ℂ Q1 (Set.univ \ {a}))
    (hQ1_tendsto : Filter.Tendsto Q1 (Filter.cocompact ℂ) (nhds 0))
    (hQ2 : AnalyticOn ℂ Q2 (Set.univ \ {a}))
    (hQ2_tendsto : Filter.Tendsto Q2 (Filter.cocompact ℂ) (nhds 0))
    (hg : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q1 w - Q2 w = g w) :
    ∀ w, w ≠ a → Q1 w = Q2 w  := by
  have h_ext_exists := entire_extension_of_diff hR hQ1 hQ2 hg h_diff_eq
  obtain ⟨h_ext, h_ext_anal, h_ext_agree⟩ := h_ext_exists
  have h_ext_tendsto :=
    cocompact_decay_of_diff_extension (a := a) hQ1_tendsto hQ2_tendsto h_ext h_ext_agree

  intro w hw

  have h_diff : Differentiable ℂ h_ext := by
    rw [← differentiableOn_univ]
    exact h_ext_anal.differentiableOn
  have h_zero : h_ext w = 0 :=
    h_diff.apply_eq_of_tendsto_cocompact w h_ext_tendsto
  have h_sub : Q1 w - Q2 w = 0 := by
    rw [← h_ext_agree w hw]; exact h_zero
  exact sub_eq_zero.mp h_sub



end Problems.residue_thm
