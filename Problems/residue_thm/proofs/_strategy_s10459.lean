import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_glue_from_local_extensions
import Problems.residue_thm.proofs.L_f_minus_sum_p_analytic_off_t
import Problems.residue_thm.proofs.L_local_extension_at_pole_exists

namespace Problems.residue_thm

-- Decompose analytic-glue into: (1) `f - ∑ P a` is analytic on `U \ T` directly,
-- (2) for each pole `a ∈ T`, a local analytic extension `g_a` exists on `Metric.ball a (R a)`
-- matching `f - ∑ P b` on the punctured ball (concretely `g_a = h a - ∑ b ∈ T.erase a, P b`),
-- and (3) a gluing lemma that, given (1)+(2), produces a global analytic `g` on `U` matching
-- `f - ∑ P a` on `U \ T`. Combinator: extract `g` from (3), then `f z = g z + ∑ P a z`
-- follows by ring from `g z = f z - ∑ P a z`.
theorem s10459
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
    ∃ (g : ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z)  := by
  have h_F_anal : AnalyticOn ℂ (fun z => f z - ∑ a ∈ T, P a z) (U \ ↑T) :=
    f_minus_sum_p_analytic_off_t hU hT hf hγ hmaps P R h hper
  have h_loc : ∀ a ∈ T, ∃ (g_a : ℂ → ℂ),
      AnalyticOn ℂ g_a (Metric.ball a (R a)) ∧
      ∀ z ∈ Metric.ball a (R a) \ {a}, g_a z = f z - ∑ b ∈ T, P b z :=
    local_extension_at_pole_exists hU hT hf hγ hmaps P R h hper
  have h_glue : ∃ (g : ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ z ∈ U \ ↑T, g z = f z - ∑ a ∈ T, P a z) :=
    analytic_glue_from_local_extensions hU hT hf hγ hmaps P R h hper h_F_anal h_loc
  obtain ⟨g, hg_anal, hg_pw⟩ := h_glue
  refine ⟨g, hg_anal, ?_⟩
  intro z hz
  have h_eq : g z = f z - ∑ a ∈ T, P a z := hg_pw z hz
  rw [h_eq]
  ring

end Problems.residue_thm
