import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_glue_witness
import Problems.residue_thm.proofs.L_residue_pole_eq_principal

namespace Problems.residue_thm

-- Decompose `global_remainder_glue` into (1) analytic-glue existence of `g`
-- with the pointwise identity on `U \ T`, and (2) residue equality at each pole.
-- Combinator: obtain `(g, hg_anal, hg_pw)` from (1); package `(g, hg_anal, hg_pw, h_res)`.
theorem s10456
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
      (∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a)  := by
  have h_glue := analytic_glue_witness hU hT hf hγ hmaps P R h hper
  have h_res := residue_pole_eq_principal hU hT hf hγ hmaps P R h hper
  obtain ⟨g, hg_anal, hg_pw⟩ := h_glue
  exact ⟨g, hg_anal, hg_pw, h_res⟩

end Problems.residue_thm
