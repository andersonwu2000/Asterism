import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_global_remainder_glue
import Problems.residue_thm.proofs.L_integral_decomp_from_pointwise
import Problems.residue_thm.proofs.L_per_pole_principal_part_data

namespace Problems.residue_thm

-- Per-pole call to `principal_part_extraction_at_singularity` plus a global gluing of the
-- analytic remainder. Three sub-goals:
--  (1) `per_pole_principal_part_data` — for each `a ∈ T`, witness the per-pole principal
--      part `P a` (analytic off `{a}`, tendsto zero at ∞) together with an isolating
--      radius `R a` and a local analytic remainder `h a` on `ball a (R a)` such that
--      `f = h a + P a` on the punctured ball.
--  (2) `global_remainder_glue` — from the per-pole data, glue the analytic remainders into
--      a single `g : ℂ → ℂ` analytic on all of `U`, deliver the pointwise decomposition
--      `f = g + ∑ P a` on `U \ T`, and derive each residue equality
--      `residue (P a) a = residue f a` via additivity of residues across analytic terms.
--  (3) `integral_decomp_from_pointwise` — from the pointwise identity on `U \ T`,
--      analyticity of `g` and each `P a`, and `γ` mapping into `U \ T`, conclude the
--      contour-integral identity by linearity of integration (each integrand is continuous
--      on `Icc 0 1`).
-- Combinator: obtain `(P, R, h, hper)` via (1); obtain `(g, hg, hpw, hres)` via (2);
-- apply (3) to convert `hpw` into the integral identity; package the existential witness.
theorem s10453
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a})) ∧
      (∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0)) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a) ∧
      (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
        (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
        ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t  := by
  have h_per := per_pole_principal_part_data hU hT hf hγ hmaps
  obtain ⟨P, R, h, hper⟩ := h_per
  have h_glue := global_remainder_glue hU hT hf hγ hmaps P R h hper
  obtain ⟨g, hg, hpw, hres⟩ := h_glue
  have hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}) :=
    fun a ha => (hper a ha).2.2.2.1
  have hPt : ∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) :=
    fun a ha => (hper a ha).2.2.2.2.1
  have h_int := integral_decomp_from_pointwise hU hT hf hγ hmaps g P hg hPa hpw
  exact ⟨g, P, hg, hPa, hPt, hres, h_int⟩



end Problems.residue_thm
