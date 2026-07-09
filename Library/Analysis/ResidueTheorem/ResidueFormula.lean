import Mathlib
import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
import Library.Analysis.ResidueTheorem.PathIntegralDecomp
import Library.Analysis.ResidueTheorem.PathIntegralZero
import Library.Analysis.ResidueTheorem.PrimitiveSubtraction
import Library.Analysis.ResidueTheorem.WindingNumberFormula
import Library.Analysis.ResidueTheorem.WindingNumberInt

/-!
# Residue Formula

This file assembles the **Residue Theorem** for meromorphic functions on simply connected domains
in `ℂ`. Given a function `f` analytic on `U \ T` (where `U` is simply connected and open and
`T` is a finite set of isolated singularities), the contour integral of `f` along any closed
curve `γ` in `U \ T` equals `2πi` times the sum of winding-number-weighted residues:
$$\int_\gamma f\,dz = 2\pi i \sum_{a \in T} n(\gamma, a) \cdot \operatorname{res}(f, a).$$

## Main statements

- `integral_principal_part_eq_winding_mul_residue`: path integral of a meromorphic function
  with a single pole at `a` equals `2πi · windingNumber(γ, a) · residue(P, a)`.
- `residue_theorem`: **Residue Theorem** — contour integral of a meromorphic function with
  finitely many poles equals `2πi` times the sum of winding-number-weighted residues.
-/

open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
open Library.Analysis.ResidueTheorem.PathIntegralDecomp
open Library.Analysis.ResidueTheorem.PathIntegralZero
open Library.Analysis.ResidueTheorem.PrimitiveSubtraction
open Library.Analysis.ResidueTheorem.WindingNumberFormula
open Library.Analysis.ResidueTheorem.WindingNumberInt

namespace Library.Analysis.ResidueTheorem.ResidueFormula

/-- The path integral of a meromorphic function `P` with a single pole at `a ∈ ℂ` along a
closed curve `γ : ℝ → ℂ` avoiding `a` equals
`2πi · windingNumber(γ, a) · Complex.residue P a`.

The proof rewrites via two sibling lemmas:
- `path_int_eq_residue_times_winding_int`: expresses `∫ P(γ t) γ'(t) dt` as
  `Complex.residue P a` times the winding-number integral.
- `winding_integral_formula`: identifies the winding-number integral with
  `2πi · windingNumber(γ, a)`. -/
theorem integral_principal_part_eq_winding_mul_residue
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) =
      2 * Real.pi * Complex.I *
        ((Complex.windingNumber γ a : ℂ) * Complex.residue P a) := by
  have hA := winding_integral_formula hγ h_avoid hclosed
  have hB := path_int_eq_residue_times_winding_int hP hP_tendsto hγ h_avoid hclosed
  rw [hB, hA]
  ring

/-- **Residue Theorem**: for a meromorphic function `f` analytic on `U \ T`, where `U ⊆ ℂ` is
simply connected and open and `T : Finset ℂ` is a finite set of poles, the contour integral of
`f` along any closed curve `γ : ℝ → ℂ` staying in `U \ T` equals `2πi` times the sum of
winding-number-weighted residues of `f` at each pole:
`∫ f(γ t) γ'(t) dt = 2πi · ∑ a ∈ T, windingNumber(γ, a) · residue(f, a)`. -/
theorem residue_theorem
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hSC : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
      ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a := by
  have h_split := analytic_remainder_principal_part_decomp hU hT hf hγ hmaps
  obtain ⟨g, P, hg, hPa, hPt, hres, hint_split⟩ := h_split
  have hmaps_U : Set.MapsTo γ (Set.Icc 0 1) U :=
    hmaps.mono_right Set.diff_subset
  have h_avoid : ∀ a ∈ T, ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a := by
    intro a ha t ht hγta
    have hmem := hmaps ht
    exact hmem.2 (hγta ▸ ha)
  have h_g_zero : (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) = 0 :=
    analytic_remainder_path_integral_zero hU hSC hg hγ hmaps_U hclosed
  have h_P_each : ∀ a ∈ T,
      (∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t) =
        2 * Real.pi * Complex.I *
          ((Complex.windingNumber γ a : ℂ) * Complex.residue (P a) a) :=
    fun a ha =>
      integral_principal_part_eq_winding_mul_residue
        (hPa a ha) (hPt a ha) hγ (h_avoid a ha) hclosed
  rw [hint_split, h_g_zero, zero_add, Finset.mul_sum]
  refine Finset.sum_congr rfl ?_
  intro a ha
  rw [h_P_each a ha, hres a ha]

end Library.Analysis.ResidueTheorem.ResidueFormula
