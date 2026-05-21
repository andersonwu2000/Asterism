import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_local_ext_candidate_analytic
import Problems.residue_thm.proofs.L_local_ext_candidate_eq_on_punctured

namespace Problems.residue_thm

-- Pick witness `g_a z = h a z - ∑ b ∈ T.erase a, P b z`.
-- Sub-goal 1 (analytic): this candidate is analytic on `Metric.ball a (R a)`
-- (since `h a` is analytic there and every `P b` with `b ≠ a` is analytic on
--  the ball because `b ∉ Metric.ball a (R a)` by separation).
-- Sub-goal 2 (identity): on the punctured ball the candidate equals
-- `f z - ∑ b ∈ T, P b z` — split `T = insert a (T.erase a)` and use
-- `f z = h a z + P a z`.
theorem s10466
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
    ∀ a ∈ T, ∃ (g_a : ℂ → ℂ),
      AnalyticOn ℂ g_a (Metric.ball a (R a)) ∧
      ∀ z ∈ Metric.ball a (R a) \ {a}, g_a z = f z - ∑ b ∈ T, P b z  := by
  intro a ha
  have h_analytic :=
    local_ext_candidate_analytic hU hT hf hγ hmaps P R h hper a ha
  have h_identity :=
    local_ext_candidate_eq_on_punctured hU hT hf hγ hmaps P R h hper a ha
  exact ⟨fun z => h a z - ∑ b ∈ T.erase a, P b z, h_analytic, h_identity⟩

end Problems.residue_thm
