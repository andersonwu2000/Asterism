import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- local_ext_candidate_analytic: AnalyticOn.sub + Finset.analyticOn_sum, using ball-separation
-- to restrict each P b (analytic on univ \ {b}) to the ball around a where b is absent.
-- entry_kind: Builder
theorem local_ext_candidate_analytic
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
    ∀ a ∈ T,
      AnalyticOn ℂ (fun z => h a z - ∑ b ∈ T.erase a, P b z)
        (Metric.ball a (R a)) := by
  intro a haT
  obtain ⟨hRpos, hball, hsep, hPana, hPtend, hhana, hfz⟩ := hper a haT
  refine hhana.sub ?_
  simp_rw [← Finset.sum_apply]
  exact Finset.analyticOn_sum _ fun b hb => by
    have hbT : b ∈ T := Finset.erase_subset a T hb
    have hbna : b ≠ a := (Finset.mem_erase.mp hb).1
    obtain ⟨_, _, _, hPb, _, _, _⟩ := hper b hbT
    apply hPb.mono
    intro z hz
    exact ⟨Set.mem_univ z, fun hzb => hsep b hbT hbna (hzb ▸ hz)⟩

end Problems.residue_thm
