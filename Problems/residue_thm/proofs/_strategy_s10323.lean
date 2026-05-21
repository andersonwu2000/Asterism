import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_pointwise_outer_radius

namespace Problems.residue_thm

-- Decompose into the pointwise statement: each pole a ∈ T has a positive
-- radius r whose punctured ball lies in U \ T, hence f is analytic there.
-- Assemble into a global function r : ℂ → ℝ via Classical.choose / dif_pos.
theorem s10323
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U) (hTU : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∃ r : ℂ → ℝ,
      (∀ a ∈ T, 0 < r a) ∧
      (∀ a ∈ T, AnalyticOn ℂ f (Metric.ball a (r a) \ {a}))  := by
  have h_pointwise :
      ∀ a ∈ T, ∃ r : ℝ, 0 < r ∧ AnalyticOn ℂ f (Metric.ball a r \ {a}) :=
    pointwise_outer_radius hU hTU hf
  classical
  refine ⟨fun a => if h : a ∈ T then (h_pointwise a h).choose else 1, ?_, ?_⟩
  · intro a ha
    change 0 < if h : a ∈ T then (h_pointwise a h).choose else 1
    rw [dif_pos ha]
    exact (h_pointwise a ha).choose_spec.1
  · intro a ha
    change AnalyticOn ℂ f (Metric.ball a (if h : a ∈ T then (h_pointwise a h).choose else 1) \ {a})
    rw [dif_pos ha]
    exact (h_pointwise a ha).choose_spec.2

end Problems.residue_thm
