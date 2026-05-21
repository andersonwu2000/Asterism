import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrand_dw_cont_on_left_half

namespace Problems.residue_thm

-- Bypass the `deriv` (not `derivWithin`) endpoint-junk trap on `[0, 1/2]`: prove the
-- integrand with `derivWithin γ (Icc 0 1)` is `ContinuousOn (Icc 0 (1/2))` (sub-goal),
-- upgrade to `IntervalIntegrable` via `ContinuousOn.intervalIntegrable_of_Icc`, then
-- swap `derivWithin γ (Icc 0 1) ↔ deriv γ` a.e. on `Ι 0 (1/2)` via `derivWithin_of_mem_nhds`
-- (`Icc 0 1 ∈ 𝓝 t` for any `t ∈ Ioo 0 (1/2) ⊆ Ioo 0 1`).
theorem s10672
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
      MeasureTheory.volume 0 (1/2)  := by
  have h_cont :=
    integrand_dw_cont_on_left_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_int_dw :
      IntervalIntegrable
        (fun t : ℝ =>
          Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
                (if s ≤ (1:ℝ)/2
                  then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                  else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
            derivWithin (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
                (if s ≤ (1:ℝ)/2
                  then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                  else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) (Set.Icc 0 1) t)
        MeasureTheory.volume 0 (1/2) :=
    h_cont.intervalIntegrable_of_Icc (by norm_num)
  apply h_int_dw.congr_ae
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1/2)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  have hmem : Set.Icc (0:ℝ) 1 ∈ nhds t :=
    Icc_mem_nhds (by linarith [ht.1]) (by linarith [ht.2])
  simp [derivWithin_of_mem_nhds hmem]

end Problems.residue_thm
