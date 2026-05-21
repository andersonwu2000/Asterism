import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_right_half_integrand_eq_on_ioo
import Problems.residue_thm.proofs.L_right_half_substituted_intintegrable

namespace Problems.residue_thm

-- On `Set.Ioo (1/2) 1` the path `γ t = α' 0 + ∫₀ᵗ ...` simplifies (by FTC + h_match)
-- to `β' (2t-1)` and `deriv γ t = 2 · derivWithin β' (Icc 0 1) (2t-1)`, so the original
-- integrand agrees with `Q (β' (2t-1)) * (2 · derivWithin β' (Icc 0 1) (2t-1))` on Ioo
-- (sub-goal `right_half_integrand_eq_on_ioo`). The substituted integrand is interval-
-- integrable on `[1/2, 1]` via continuity (sub-goal `right_half_substituted_intintegrable`).
-- Combinator: `IntervalIntegrable.congr_ae`, using `Ioo_ae_eq_Ioc` to lift the Ioo equality
-- to a.e.-equality on `Ι (1/2) 1 = Ioc (1/2) 1`.
theorem s10673
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    IntervalIntegrable
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t)
      MeasureTheory.volume (1/2) 1  := by
  have h_eq_on :=
    right_half_integrand_eq_on_ioo hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_simp_ii :=
    right_half_substituted_intintegrable hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv

  refine h_simp_ii.congr_ae ?_
  have h_uIoc : Set.uIoc (1/2 : ℝ) 1 = Set.Ioc (1/2 : ℝ) 1 :=
    Set.uIoc_of_le (by norm_num)
  rw [show Set.uIoc (1/2 : ℝ) 1 = Set.Ioc (1/2 : ℝ) 1 from h_uIoc,
      ← MeasureTheory.Measure.restrict_congr_set
        (s := Set.Ioo (1/2 : ℝ) 1) (t := Set.Ioc (1/2 : ℝ) 1) MeasureTheory.Ioo_ae_eq_Ioc]
  filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with t ht
  exact (h_eq_on ht).symm


end Problems.residue_thm
