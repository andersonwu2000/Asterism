import Library.Analysis.ResidueTheorem.HolomorphicPart
import Library.Analysis.ResidueTheorem.InnerPrincipalPart

/-!
# Principal part extraction at an isolated singularity

Given a function `f` analytic on a punctured ball `Metric.ball z₀ R \ {z₀}`, this file
establishes that `f` decomposes as the sum of a holomorphic part `g` (analytic on the full
ball `Metric.ball z₀ R`) and a principal part `P` (analytic on `ℂ \ {z₀}`, vanishing at
infinity). The proof assembles the holomorphic part from `HolomorphicPart` and the principal
part from `InnerPrincipalPart`, then appeals to the annular Cauchy identity to verify the
pointwise equality.

## Main statements

- `principal_part_extraction_at_singularity`: existence of the decomposition `f = g + P`.
- `cauchy_annulus_add_eq`: the pointwise identity `f z = g z + P z` given Cauchy kernel
  representations of `g` and `P`.
-/

open Library.Analysis.ResidueTheorem.HolomorphicPart
open Library.Analysis.ResidueTheorem.InnerPrincipalPart

namespace Library.Analysis.ResidueTheorem.PrincipalPartExtraction

/-- **Principal part extraction**: given `f` analytic on the punctured ball
`Metric.ball z₀ R \ {z₀}`, there exist `P` (the principal part) and `g` (the holomorphic part)
such that `P` is analytic on `Set.univ \ {z₀}` and tends to `0` at infinity,
`g` is analytic on the full ball `Metric.ball z₀ R`, and
`f z = g z + P z` for all `z ∈ Metric.ball z₀ R \ {z₀}`. -/
theorem principal_part_extraction_at_singularity
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (P g : ℂ → ℂ),
      AnalyticOn ℂ P (Set.univ \ {z₀}) ∧
      Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z := by
  have h_g_exists := exists_analyticOn_cauchy_kernel hR hf
  have h_P_exists := inner_principal_part_exists hR hf
  obtain ⟨g, hg_an, hg_eq⟩ := h_g_exists
  obtain ⟨P, hP_an, hP_t, hP_eq⟩ := h_P_exists
  exact ⟨P, g, hP_an, hP_t, hg_an, cauchy_annulus_sum_formula hR hf g P hg_eq hP_eq⟩

/-- Given the Cauchy kernel representation of `g` and the annular Cauchy representation of `P`,
the pointwise identity `f z = g z + P z` holds on the punctured ball
`Metric.ball z₀ R \ {z₀}`. -/
theorem cauchy_annulus_add_eq
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (g P : ℂ → ℂ)
    (hg_eq : ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
      g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, r), f w / (w - z))
    (hP_eq : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
      P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, ε), f w / (w - z))) :
    ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z := by
  exact cauchy_annulus_sum_formula hR hf g P hg_eq hP_eq

end Library.Analysis.ResidueTheorem.PrincipalPartExtraction
