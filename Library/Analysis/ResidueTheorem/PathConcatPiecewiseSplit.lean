import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Calculus.ContDiff.Deriv
import Mathlib.MeasureTheory.Integral.IntervalIntegral.Basic

/-!
# Piecewise path integral splitting

This file collects splitting lemmas for piecewise-defined integrands arising from concatenated
paths. Given two $C^1$ curves `α' β' : ℝ → ℂ` on `[0, 1]`, the concatenated path uses a
piecewise integrand switching at the midpoint `1/2`.

## Main statements

- `piecewise_integral_add_adjacent_half`: interval additivity of the piecewise integral at `1/2`.
- `piecewise_integral_split_clean_on_ioo`: on `Ioo (1/2) 1` the piecewise integral splits into
  clean `α'`- and `β'`-integrals.
- `piecewise_split_eq_pointwise_on_ioo`: pointwise split including the base point `α' 0`.
- `piecewise_f_eveq_right_split_on_ioo`: `Filter.EventuallyEq` version, used to differentiate
  the concatenated path on the open right half.
-/

namespace Library.Analysis.ResidueTheorem.PathConcatPiecewiseSplit

/-- Interval additivity of the piecewise integrand at the midpoint `1/2`.

For $t \in [1/2, 1]$, the integral from `0` to `t` of the piecewise function
$s \mapsto \begin{cases} 2\,\alpha'(2s) & s \le 1/2 \\ 2\,\beta'(2s-1) & s > 1/2 \end{cases}$
equals the integral from `0` to `1/2` plus the integral from `1/2` to `t`.
Integrability on the left half follows from `ContinuousOn.intervalIntegrable`; on the right
half from `IntervalIntegrable.congr_ae` against the continuous `β'`-branch.
Closed by `intervalIntegral.integral_add_adjacent_intervals`. -/
theorem piecewise_integral_add_adjacent_half
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_h_match : α' 1 = β' 0)
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      (∫ s in (0:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = (∫ s in (0:ℝ)..((1:ℝ)/2),
            (if s ≤ (1:ℝ)/2
              then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
              else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
          + (∫ s in ((1:ℝ)/2:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) := by
  intro t ht
  set f : ℝ → ℂ := fun s =>
    if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                    else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)
  have hcα : ContinuousOn (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
      (Set.Icc 0 (1/2)) :=
    continuousOn_const.mul
      ((hα'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).comp
        (continuousOn_const.mul continuousOn_id)
        (fun s hs => ⟨by linarith [hs.1], by linarith [hs.2]⟩))
  have hcβ : ContinuousOn (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc (1/2) 1) :=
    continuousOn_const.mul
      ((hβ'.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).comp
        ((continuousOn_const.mul continuousOn_id).sub continuousOn_const)
        (fun s hs => ⟨by linarith [hs.1], by linarith [hs.2]⟩))
  have hfi_left : IntervalIntegrable f MeasureTheory.volume 0 (1/2) := by
    apply ContinuousOn.intervalIntegrable
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1/2)]
    exact hcα.congr fun s hs => by
      simp only [Set.mem_Icc] at hs
      simp only [f, if_pos hs.2]
  have hfi_right : IntervalIntegrable f MeasureTheory.volume (1/2) t := by
    have hβ_int : IntervalIntegrable (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2*s-1))
        MeasureTheory.volume (1/2) t := by
      apply ContinuousOn.intervalIntegrable
      rw [Set.uIcc_of_le ht.1]
      exact hcβ.mono (Set.Icc_subset_Icc_right ht.2)
    apply hβ_int.congr_ae
    rw [Set.uIoc_of_le ht.1]
    filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioc] with s hs
    simp only [Set.mem_Ioc] at hs
    simp only [f, if_neg (show ¬ s ≤ (1:ℝ)/2 from by linarith [hs.1])]
  symm
  exact intervalIntegral.integral_add_adjacent_intervals hfi_left hfi_right


/-- On `Ioo (1/2) 1`, the piecewise integral from `0` to `u` splits into the clean
`α'`-integral from `0` to `1/2` plus the `β'`-integral from `1/2` to `u`.

Continuity of each branch on its domain yields `IntervalIntegrable` for both the piecewise
function and the individual branches via `ContinuousOn.intervalIntegrable_of_Icc`. Applying
`intervalIntegral.integral_add_adjacent_intervals` and simplifying each piece by pointwise
equality of the integrand on its respective interval closes the goal. -/
theorem piecewise_integral_split_clean_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ u ∈ Set.Ioo ((1:ℝ)/2) 1,
      (∫ s in (0:ℝ)..u,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = (∫ s in (0:ℝ)..((1:ℝ)/2), 2 * derivWithin α' (Set.Icc 0 1) (2*s))
          + ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1) := by
  intro u hu
  have h0h : (0:ℝ) ≤ 1/2 := by norm_num
  have hhu : (1:ℝ)/2 ≤ u := hu.1.le
  have hα'dw : ContinuousOn (derivWithin α' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hα'.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl
  have hβ'dw : ContinuousOn (derivWithin β' (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hβ'.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl
  have hα_cont : ContinuousOn (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
      (Set.Icc 0 (1/2)) := by
    apply ContinuousOn.mul continuousOn_const
    apply ContinuousOn.comp hα'dw
    · exact (continuous_const.mul continuous_id).continuousOn
    · intro s hs; exact ⟨by linarith [hs.1], by linarith [hs.2]⟩
  have hβ_cont : ContinuousOn (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      (Set.Icc (1/2) u) := by
    apply ContinuousOn.mul continuousOn_const
    apply ContinuousOn.comp hβ'dw
    · exact ((continuous_const.mul continuous_id).sub continuous_const).continuousOn
    · intro s hs; exact ⟨by linarith [hs.1], by linarith [hs.2, hu.2]⟩
  have hα_intbl : IntervalIntegrable (fun s => (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s))
      MeasureTheory.volume 0 (1/2) :=
    hα_cont.intervalIntegrable_of_Icc h0h
  have hβ_intbl : IntervalIntegrable (fun s => (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1))
      MeasureTheory.volume (1/2) u :=
    hβ_cont.intervalIntegrable_of_Icc hhu
  have hpw_int1 : IntervalIntegrable
      (fun s => if s ≤ (1:ℝ)/2 then (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      MeasureTheory.volume 0 (1/2) := by
    rw [intervalIntegrable_iff, Set.uIoc_of_le h0h]
    apply (hα_intbl.1).congr_fun _ measurableSet_Ioc
    intro s hs
    change (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s) =
        if s ≤ 1/2 then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)
    rw [if_pos hs.2]
  have hpw_int2 : IntervalIntegrable
      (fun s => if s ≤ (1:ℝ)/2 then (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      MeasureTheory.volume (1/2) u := by
    rw [intervalIntegrable_iff, Set.uIoc_of_le hhu]
    apply (hβ_intbl.1).congr_fun _ measurableSet_Ioc
    intro s hs
    change (2:ℂ) * derivWithin β' (Set.Icc 0 1) (2 * s - 1) =
        if s ≤ 1/2 then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)
    rw [if_neg (not_le.mpr hs.1)]
  rw [← intervalIntegral.integral_add_adjacent_intervals hpw_int1 hpw_int2]
  congr 1
  · apply intervalIntegral.integral_congr
    intro s hs
    rw [Set.uIcc_of_le h0h] at hs
    change (if s ≤ 1/2 then (2:ℂ) * derivWithin α' (Set.Icc 0 1) (2 * s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1)) =
        2 * derivWithin α' (Set.Icc 0 1) (2 * s)
    rw [if_pos hs.2]
  · apply intervalIntegral.integral_congr_ae
    rw [Set.uIoc_of_le hhu]
    apply MeasureTheory.ae_of_all MeasureTheory.volume
    intro s hs
    rw [if_neg (not_le.mpr hs.1)]

/-- Pointwise form of the integral split on `Ioo (1/2) 1`, with the base point `α' 0` added.

For `u ∈ Ioo (1/2) 1`, `α' 0 + ∫₀ᵘ f` equals `(α' 0 + ∫₀^{1/2} 2α'(2s)) + ∫_{1/2}^u 2β'(2s-1)`.
Follows from `piecewise_integral_split_clean_on_ioo` by `add_assoc`. -/
theorem piecewise_split_eq_pointwise_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ u ∈ Set.Ioo ((1:ℝ)/2) 1,
      (α' 0 + ∫ s in (0:ℝ)..u,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2),
                  2 * derivWithin α' (Set.Icc 0 1) (2*s)) +
          ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)  := by
  intro u hu
  have h_split := piecewise_integral_split_clean_on_ioo hα' hβ' u hu
  rw [h_split, add_assoc]

/-- `Filter.EventuallyEq` version of the piecewise integral split at points `t ∈ Ioo (1/2) 1`.

`piecewise_split_eq_pointwise_on_ioo` gives pointwise equality on `Ioo (1/2) 1`; since this
set is open, `isOpen_Ioo.mem_nhds ht` makes it a neighbourhood of `t`, and
`Filter.eventuallyEq_of_mem` converts pointwise equality to `=ᶠ[nhds t]`. -/
theorem piecewise_f_eveq_right_split_on_ioo
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      (fun u : ℝ => α' 0 + ∫ s in (0:ℝ)..u,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        =ᶠ[nhds t]
        (fun u : ℝ => (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2),
                  2 * derivWithin α' (Set.Icc 0 1) (2*s)) +
          ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))  := by
  intro t ht
  have h_pt := piecewise_split_eq_pointwise_on_ioo hα' hβ'
  exact (Filter.eventuallyEq_of_mem (isOpen_Ioo.mem_nhds ht) h_pt)

end Library.Analysis.ResidueTheorem.PathConcatPiecewiseSplit
