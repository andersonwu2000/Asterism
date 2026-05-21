import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- local_ext_candidate_eq_on_punctured: Finset.add_sum_erase + f=h+P identity closes
-- the algebraic identity h a z - ∑_{b≠a} P b z = f z - ∑_b P b z on the punctured ball
-- entry_kind: Builder
theorem local_ext_candidate_eq_on_punctured
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ)
    (hper : ∀ a ∈ T,
      0 < R a ∧
      Metric.ball a (R a) ⊆ U ∧
      (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
      AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
      Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    ∀ a ∈ T, ∀ z ∈ Metric.ball a (R a) \ {a},
      h a z - ∑ b ∈ T.erase a, P b z = f z - ∑ b ∈ T, P b z := by
  intro a haT z hzball
  obtain ⟨_, _, _, _, _, _, hfz⟩ := hper a haT
  have hfz' := hfz z hzball
  have hsum : ∑ b ∈ T, P b z = P a z + ∑ b ∈ T.erase a, P b z := by
    rw [← Finset.add_sum_erase _ _ haT]
  simp only [hfz', hsum]; ring

end Problems.residue_thm
