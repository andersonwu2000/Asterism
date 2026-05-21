import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- f_minus_sum_p_analytic_off_t: AnalyticOn.sub + Finset.analyticOn_fun_sum; mono U\T ⊆ univ\{a}
-- entry_kind: Builder
theorem f_minus_sum_p_analytic_off_t
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
    AnalyticOn ℂ (fun z => f z - ∑ a ∈ T, P a z) (U \ ↑T) := by
  apply hf.sub
  apply T.analyticOn_fun_sum
  intro a ha
  apply (hper a ha).2.2.2.1.mono
  intro z hz
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
  intro heq
  exact hz.2 (heq ▸ Finset.mem_coe.mpr ha)
end Problems.residue_thm
