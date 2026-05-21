import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_split_residue_term
import Problems.residue_thm.proofs.L_residue_subtracted_path_int_zero

namespace Problems.residue_thm

-- Subtract the simple-pole residue piece `r/(z-a)` (r := residue P a) from `P` to land in
-- a zero-residue principal-part regime whose closed-path integral vanishes; then split the
-- subtraction back out by integral linearity to recover the target identity.
--   * residue_subtracted_path_int_zero (Backward): ∫₀¹ (P(γt) - r/(γt-a)) γ'(t) dt = 0
--     — Q := P - r/(·-a) is analytic on ℂ\{a}, decays at ∞, residue 0 at `a`, so it admits
--       a primitive on ℂ\{a} and the closed-loop integral collapses.
--   * path_int_split_residue_term (Builder): the integrand-subtraction split — pure interval-
--     integral linearity using `intervalIntegral.integral_sub` + `intervalIntegral.integral_const_mul`
--     once both summands are interval-integrable (P∘γ·γ' continuous; (γ'-)/(γ-a) continuous via h_avoid).
-- Combinator: hA gives the residue-subtracted integral = 0; hB rewrites it as A - r·B;
-- chaining `rw [← hB]; exact hA` yields A - r·B = 0, then `sub_eq_zero.mp` flips to A = r·B.
theorem s10476
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
      = Complex.residue P a * (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a))  := by
  have hA := residue_subtracted_path_int_zero hP hP_tendsto hγ h_avoid hclosed
  have hB := path_int_split_residue_term hP hP_tendsto hγ h_avoid hclosed
  have h_sub_zero : (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) -
      Complex.residue P a * (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 0 := by
    rw [← hB]; exact hA
  exact sub_eq_zero.mp h_sub_zero

end Problems.residue_thm
